from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction as db_transaction
import math

from slots.models import ParkingSlot
from vehicles.models import Vehicle
from bookings.models import Booking
from .models import Transaction
from .serializers import TransactionSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def vehicle_entry(request):
    """
    Called by ANPR module when vehicle arrives at entry gate.
    Expects: { "plate_number": "UP32AB1234" }
    """
    plate_number = request.data.get('plate_number', '').upper().strip()

    if not plate_number:
        return Response({'error': 'Plate number is required'}, status=400)

    # Check if vehicle already has an open transaction
    open_transaction = Transaction.objects.filter(
        vehicle__vehicle_no=plate_number,
        exit_time__isnull=True
    ).first()

    if open_transaction:
        return Response({
            'error': f'Vehicle {plate_number} is already parked in slot {open_transaction.slot.slot_id}'
        }, status=400)

    # Get or create vehicle
    vehicle, created = Vehicle.objects.get_or_create(
        vehicle_no=plate_number,
        defaults={'owner_name': 'Walk-in', 'vehicle_type': 'Compact'}
    )

    # Check for active pre-booking
    today = timezone.now().date()
    current_time = timezone.now().time()

    active_booking = Booking.objects.filter(
        vehicle=vehicle,
        booking_date=today,
        start_time__lte=current_time,
        end_time__gte=current_time,
        status='CONFIRMED'
    ).first()

    with db_transaction.atomic():
        if active_booking:
            # Pre-booked vehicle — use reserved slot
            slot = active_booking.slot
            active_booking.status = 'ACTIVE'
            active_booking.save()
            entry_type = 'PRE-BOOKED'
        else:
            # Walk-in — find first available slot
            slot = ParkingSlot.objects.select_for_update().filter(
                is_occupied=False,
                is_active=True,
                status='available'
            ).first()

            if not slot:
                return Response({'error': 'Parking lot is full'}, status=400)

            entry_type = 'WALK-IN'

        # Lock the slot
        slot.is_occupied = True
        slot.status = 'occupied'
        slot.save()

        # Create transaction
        trans = Transaction.objects.create(
            vehicle=vehicle,
            slot=slot,
            booking=active_booking
        )

    return Response({
        'success': True,
        'message': f'Welcome! Vehicle {plate_number} assigned to slot {slot.slot_id}',
        'entry_type': entry_type,
        'transaction_id': trans.id,
        'slot_id': slot.slot_id,
        'zone': slot.zone_name,
        'entry_time': trans.entry_time
    }, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def vehicle_exit(request):
    """
    Called by ANPR module when vehicle arrives at exit gate.
    Expects: { "plate_number": "UP32AB1234" }
    """
    plate_number = request.data.get('plate_number', '').upper().strip()

    if not plate_number:
        return Response({'error': 'Plate number is required'}, status=400)

    # Find open transaction
    try:
        trans = Transaction.objects.get(
            vehicle__vehicle_no=plate_number,
            exit_time__isnull=True
        )
    except Transaction.DoesNotExist:
        return Response({'error': f'No active transaction found for {plate_number}'}, status=404)

    # Calculate duration and fee
    exit_time = timezone.now()
    duration = exit_time - trans.entry_time
    duration_hours = duration.total_seconds() / 3600
    duration_hours = max(1, math.ceil(duration_hours))  # minimum 1 hour

    hourly_rate = 50  # ₹50 per hour
    total_fee = duration_hours * hourly_rate

    # Update transaction
    trans.exit_time = exit_time
    trans.total_fee = total_fee
    trans.save()

    return Response({
        'success': True,
        'message': f'Vehicle {plate_number} exit processed',
        'transaction_id': trans.id,
        'slot_id': trans.slot.slot_id,
        'entry_time': trans.entry_time,
        'exit_time': exit_time,
        'duration_hours': duration_hours,
        'total_fee': f'₹{total_fee}',
        'payment_status': 'PENDING'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def transaction_list(request):
    transactions = Transaction.objects.all().order_by('-entry_time')
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def active_transactions(request):
    transactions = Transaction.objects.filter(exit_time__isnull=True)
    serializer = TransactionSerializer(transactions, many=True)
    return Response({
        'currently_parked': transactions.count(),
        'transactions': serializer.data
    })