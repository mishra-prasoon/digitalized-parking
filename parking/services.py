import math
from django.db import transaction as db_transaction
from django.utils import timezone

from core.models import ParkingSlot
from booking.models import Booking
from .models import Tariff, Transaction

EARLY_ENTRY_GRACE = timezone.timedelta(minutes=15)
WALKIN_BUFFER = timezone.timedelta(minutes=60)


class AllocationError(Exception):
    pass


def _matching_booking(vehicle, now):
    return Booking.objects.filter(
        vehicle=vehicle,
        status=Booking.Status.CONFIRMED,
        start_time__lte=now + EARLY_ENTRY_GRACE,
        end_time__gte=now,
    ).select_related('slot').first()


@db_transaction.atomic
def allocate_and_check_in(vehicle):
    now = timezone.now()

    if Transaction.objects.filter(vehicle=vehicle, status=Transaction.Status.OPEN).exists():
        raise AllocationError('Vehicle already has an open session.')

    booking = _matching_booking(vehicle, now)

    if booking:
        slot = ParkingSlot.objects.select_for_update().get(pk=booking.slot_id)
        booking.status = Booking.Status.COMPLETED
        booking.save(update_fields=['status'])
    else:
        buffer_cutoff = now + WALKIN_BUFFER
        reserved_slot_ids = Booking.objects.filter(
            status=Booking.Status.CONFIRMED,
            start_time__lte=buffer_cutoff,
            end_time__gte=now,
        ).values_list('slot_id', flat=True)

        slot = (
            ParkingSlot.objects.select_for_update(skip_locked=True)
            .filter(is_active=True)
            .exclude(pk__in=reserved_slot_ids)
            .exclude(transactions__status=Transaction.Status.OPEN)
            .order_by('slot_id')
            .first()
        )
        if slot is None:
            raise AllocationError('Lot full.')

    txn = Transaction.objects.create(vehicle=vehicle, slot=slot, booking=booking)
    return txn


def calculate_fee(entry_time, exit_time, tariff):
    duration = exit_time - entry_time
    hours = max(1, math.ceil(duration.total_seconds() / 3600))
    fee = hours * tariff.hourly_rate
    return max(fee, tariff.min_charge)


@db_transaction.atomic
def check_out(vehicle):
    txn = Transaction.objects.select_for_update().filter(
        vehicle=vehicle, status=Transaction.Status.OPEN
    ).first()
    if txn is None:
        raise AllocationError('No open session for this vehicle.')

    tariff = Tariff.objects.filter(is_active=True).first()
    if tariff is None:
        raise AllocationError('No active tariff configured.')

    now = timezone.now()
    fee = calculate_fee(txn.entry_time, now, tariff)

    txn.exit_time = now
    txn.fee = fee
    txn.status = Transaction.Status.AWAITING_PAYMENT
    txn.save(update_fields=['exit_time', 'fee', 'status'])
    return txn


@db_transaction.atomic
def close_transaction(txn):
    """Call after payment succeeds (Phase 7)."""
    txn.status = Transaction.Status.CLOSED
    txn.save(update_fields=['status'])
    return txn
