from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
import math

from slots.models import ParkingSlot
from vehicles.models import Vehicle
from .models import Booking
from .serializers import BookingSerializer

from rest_framework.permissions import AllowAny, IsAuthenticated

BOOKING_RATE = 20   # ₹20 per hour for pre-booking
PARKING_RATE = 50   # ₹50 per hour for actual parking


def sync_slot_statuses():
    """Auto-sync slot statuses based on current time."""
    now = timezone.now()
    today = now.date()
    current_time = now.time()

    # Active confirmed bookings right now
    active_booking_slots = Booking.objects.filter(
        booking_date=today,
        start_time__lte=current_time,
        end_time__gte=current_time,
        status='CONFIRMED',
        booking_paid=True
    ).values_list('slot_id', flat=True)

    # Mark as booked
    ParkingSlot.objects.filter(
        slot_id__in=active_booking_slots,
        is_occupied=False
    ).update(status='booked')

    # Release expired bookings
    ParkingSlot.objects.filter(
        status='booked',
        is_occupied=False
    ).exclude(slot_id__in=active_booking_slots).update(status='available')

    # Mark NO_SHOW for bookings whose end_time has passed without entry
    from transactions.models import Transaction
    expired_bookings = Booking.objects.filter(
        booking_date=today,
        end_time__lt=current_time,
        status='CONFIRMED',
        booking_paid=True
    )
    for booking in expired_bookings:
        # Check if vehicle made entry
        has_entry = Transaction.objects.filter(
            booking=booking,
            exit_time__isnull=True
        ).exists()
        if not has_entry:
            booking.status = 'NO_SHOW'
            booking.save()


@api_view(['POST'])
@permission_classes([AllowAny])
def create_booking(request):
    """
    Step 1 of booking — validate and calculate amount.
    Returns booking details + amount to pay.
    Does NOT create booking yet — booking created after payment.
    """
    plate_number = request.data.get('plate_number', '').upper().strip()
    booking_date = request.data.get('booking_date')
    start_time = request.data.get('start_time')
    end_time = request.data.get('end_time')
    zone_name = request.data.get('zone_name', '')
    slot_type = request.data.get('slot_type', 'Compact')

    if not all([plate_number, booking_date, start_time, end_time]):
        return Response({'error': 'All fields are required'}, status=400)

    try:
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(start_time, '%H:%M').time()
        end_time_obj = datetime.strptime(end_time, '%H:%M').time()
    except ValueError:
        return Response({'error': 'Invalid date/time format'}, status=400)

    if booking_date_obj < timezone.now().date():
        return Response({'error': 'Booking date cannot be in the past'}, status=400)

    if start_time_obj >= end_time_obj:
        return Response({'error': 'Start time must be before end time'}, status=400)

    # Calculate duration and amount
    start_dt = datetime.combine(booking_date_obj, start_time_obj)
    end_dt = datetime.combine(booking_date_obj, end_time_obj)
    duration_hours = max(1, math.ceil((end_dt - start_dt).total_seconds() / 3600))
    booking_amount = duration_hours * BOOKING_RATE

    # Find available slot
    conflicting_slots = Booking.objects.filter(
        booking_date=booking_date_obj,
        status__in=['CONFIRMED', 'ACTIVE'],
        booking_paid=True,
        start_time__lt=end_time_obj,
        end_time__gt=start_time_obj
    ).values_list('slot_id', flat=True)

    available_slots = ParkingSlot.objects.filter(
        is_active=True,
        slot_type=slot_type
    ).exclude(slot_id__in=conflicting_slots)

    if zone_name:
        available_slots = available_slots.filter(zone_name=zone_name)

    if not available_slots.exists():
        return Response({
            'error': 'No slots available for selected date, time and preferences'
        }, status=400)

    slot = available_slots.first()

    return Response({
        'success': True,
        'slot_id': slot.slot_id,
        'zone': slot.zone_name,
        'slot_type': slot.slot_type,
        'plate_number': plate_number,
        'booking_date': booking_date,
        'start_time': start_time,
        'end_time': end_time,
        'duration_hours': duration_hours,
        'booking_amount': booking_amount,
        'parking_rate': PARKING_RATE,
        'message': f'Slot {slot.slot_id} available. Pay ₹{booking_amount} to confirm.'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def create_booking_order(request):
    """
    Create Razorpay order for booking payment.
    """
    from django.conf import settings
    import razorpay

    plate_number = request.data.get('plate_number', '').upper().strip()
    booking_date = request.data.get('booking_date')
    start_time = request.data.get('start_time')
    end_time = request.data.get('end_time')
    slot_id = request.data.get('slot_id')
    booking_amount = request.data.get('booking_amount')
    slot_type = request.data.get('slot_type', 'Compact')

    if not all([plate_number, booking_date, start_time, end_time, slot_id, booking_amount]):
        return Response({'error': 'Missing required fields'}, status=400)

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    amount_paise = int(float(booking_amount) * 100)
    if amount_paise < 100:
        amount_paise = 100

    try:
        order = client.order.create(data={
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': f'booking_{plate_number}_{booking_date}',
            'notes': {
                'plate': plate_number,
                'slot': slot_id,
                'date': booking_date
            }
        })

        return Response({
            'success': True,
            'order_id': order['id'],
            'amount': amount_paise,
            'key_id': settings.RAZORPAY_KEY_ID,
            'slot_id': slot_id,
            'plate_number': plate_number,
            'booking_date': booking_date,
            'start_time': start_time,
            'end_time': end_time,
            'slot_type': slot_type,
            'booking_amount': booking_amount
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_booking(request):
    """
    After Razorpay payment success — verify and create booking.
    """
    import razorpay
    import hmac
    import hashlib
    from django.conf import settings

    razorpay_order_id = request.data.get('razorpay_order_id')
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    razorpay_signature = request.data.get('razorpay_signature')
    plate_number = request.data.get('plate_number', '').upper().strip()
    booking_date = request.data.get('booking_date')
    start_time = request.data.get('start_time')
    end_time = request.data.get('end_time')
    slot_id = request.data.get('slot_id')
    booking_amount = request.data.get('booking_amount')
    slot_type = request.data.get('slot_type', 'Compact')

    # Verify signature
    key_secret = settings.RAZORPAY_KEY_SECRET.encode('utf-8')
    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
    generated_sig = hmac.new(key_secret, message, hashlib.sha256).hexdigest()

    if generated_sig != razorpay_signature:
        return Response({'error': 'Payment verification failed'}, status=400)

    try:
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(start_time, '%H:%M').time()
        end_time_obj = datetime.strptime(end_time, '%H:%M').time()

        slot = ParkingSlot.objects.get(slot_id=slot_id)
        vehicle, _ = Vehicle.objects.get_or_create(
            vehicle_no=plate_number,
            defaults={'owner_name': 'User', 'vehicle_type': slot_type}
        )

        user = request.user if request.user.is_authenticated else get_default_user()

        booking = Booking.objects.create(
            user=user,
            vehicle=vehicle,
            slot=slot,
            booking_date=booking_date_obj,
            start_time=start_time_obj,
            end_time=end_time_obj,
            status='CONFIRMED',
            booking_amount=booking_amount,
            booking_payment_id=razorpay_payment_id,
            booking_order_id=razorpay_order_id,
            booking_paid=True
        )

        # Update slot status
        sync_slot_statuses()

        return Response({
            'success': True,
            'message': f'Booking confirmed! Slot {slot_id} reserved for {plate_number}',
            'booking_id': booking.id,
            'slot_id': slot_id,
            'zone': slot.zone_name,
            'plate_number': plate_number,
            'booking_date': booking_date,
            'start_time': start_time,
            'end_time': end_time,
            'booking_amount_paid': f'₹{booking_amount}',
            'status': 'CONFIRMED'
        })

    except ParkingSlot.DoesNotExist:
        return Response({'error': 'Slot not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


def get_default_user():
    from django.contrib.auth.models import User
    return User.objects.filter(is_superuser=True).first()


@api_view(['GET'])
@permission_classes([AllowAny])
def booking_list(request):
    sync_slot_statuses()
    bookings = Booking.objects.all().order_by('-created_at')
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def cancel_booking(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        if booking.status in ['COMPLETED', 'CANCELLED', 'NO_SHOW', 'ACTIVE']:
            return Response({'error': f'Cannot cancel — booking is {booking.status}'}, status=400)
        booking.status = 'CANCELLED'
        booking.save()
        # Free the slot
        booking.slot.status = 'available'
        booking.slot.save()
        return Response({
            'success': True,
            'message': f'Booking #{booking_id} cancelled. Note: Booking amount is non-refundable.'
        })
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=404)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_availability(request):
    sync_slot_statuses()
    booking_date = request.query_params.get('booking_date')
    start_time = request.query_params.get('start_time')
    end_time = request.query_params.get('end_time')
    slot_type = request.query_params.get('slot_type', '')
    zone_name = request.query_params.get('zone_name', '')

    if not all([booking_date, start_time, end_time]):
        return Response({'error': 'booking_date, start_time, end_time required'}, status=400)

    try:
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(start_time, '%H:%M').time()
        end_time_obj = datetime.strptime(end_time, '%H:%M').time()
    except ValueError:
        return Response({'error': 'Invalid format'}, status=400)

    conflicting = Booking.objects.filter(
        booking_date=booking_date_obj,
        status__in=['CONFIRMED', 'ACTIVE'],
        booking_paid=True,
        start_time__lt=end_time_obj,
        end_time__gt=start_time_obj
    ).values_list('slot_id', flat=True)

    available = ParkingSlot.objects.filter(is_active=True).exclude(slot_id__in=conflicting)
    if slot_type:
        available = available.filter(slot_type=slot_type)
    if zone_name:
        available = available.filter(zone_name=zone_name)

    from slots.serializers import ParkingSlotSerializer
    return Response({
        'available_count': available.count(),
        'slots': ParkingSlotSerializer(available, many=True).data
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def search_slots(request):
    """
    Zone-based slot search for pre-booking.
    Input: { date, start_time, duration_minutes }
    Output: zones with available slot counts and price
    """
    from datetime import datetime, timedelta
    from django.db.models import Count

    booking_date = request.data.get('date')
    start_time = request.data.get('start_time')
    duration_minutes = int(request.data.get('duration_minutes', 60))

    if not all([booking_date, start_time]):
        return Response({'error': 'date and start_time are required'}, status=400)

    try:
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_dt = datetime.strptime(f"{booking_date} {start_time}", '%Y-%m-%d %H:%M')
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        end_time_obj = end_dt.time()
        start_time_obj = start_dt.time()
    except ValueError:
        return Response({'error': 'Invalid date or time format'}, status=400)

    if booking_date_obj < timezone.now().date():
        return Response({'error': 'Date cannot be in the past'}, status=400)

    duration_hours = duration_minutes / 60
    price = max(20, round(duration_hours * BOOKING_RATE))

    def get_zone_availability(s_time, e_time):
        # Slots blocked by overlapping confirmed bookings
        blocked_slots = Booking.objects.filter(
            booking_date=booking_date_obj,
            status__in=['CONFIRMED', 'ACTIVE'],
            booking_paid=True,
            start_time__lt=e_time,
            end_time__gt=s_time
        ).values_list('slot_id', flat=True)

        # All active slots not blocked by bookings
        # NOTE: Do NOT filter by is_occupied — irrelevant for future booking
        available = ParkingSlot.objects.filter(
            is_active=True
        ).exclude(slot_id__in=blocked_slots)

        # Group by zone
        zones = {}
        for slot in available:
            if slot.zone_name not in zones:
                zones[slot.zone_name] = 0
            zones[slot.zone_name] += 1

        return zones

    # Primary search
    zones = get_zone_availability(start_time_obj, end_time_obj)
    total_available = sum(zones.values())

    if total_available > 0:
        zone_list = [
            {
                'zone_name': zone,
                'available_count': count,
                'price': price,
                'duration_minutes': duration_minutes,
                'start_time': start_time,
                'end_time': end_dt.strftime('%H:%M'),
                'date': booking_date
            }
            for zone, count in zones.items()
            if count > 0
        ]
        return Response({
            'success': True,
            'total_available': total_available,
            'zones': zone_list,
            'searched_date': booking_date,
            'searched_start': start_time,
            'searched_end': end_dt.strftime('%H:%M'),
            'duration_minutes': duration_minutes,
            'suggestion': None
        })

    # No availability — try +30 minutes
    alt_start = start_dt + timedelta(minutes=30)
    alt_end = alt_start + timedelta(minutes=duration_minutes)
    alt_zones = get_zone_availability(alt_start.time(), alt_end.time())
    alt_total = sum(alt_zones.values())

    suggestion = None
    if alt_total > 0:
        suggestion = {
            'message': f'No slots for {start_dt.strftime("%I:%M %p")} – {end_dt.strftime("%I:%M %p")}. '
                       f'Try {alt_start.strftime("%I:%M %p")} – {alt_end.strftime("%I:%M %p")} '
                       f'({alt_total} available)',
            'alt_start': alt_start.strftime('%H:%M'),
            'alt_end': alt_end.strftime('%H:%M'),
            'alt_start_display': alt_start.strftime('%I:%M %p'),
            'alt_end_display': alt_end.strftime('%I:%M %p'),
            'alt_total': alt_total
        }

    return Response({
        'success': False,
        'total_available': 0,
        'zones': [],
        'suggestion': suggestion,
        'searched_date': booking_date,
        'searched_start': start_time,
        'searched_end': end_dt.strftime('%H:%M'),
        'duration_minutes': duration_minutes
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def initiate_booking(request):
    """
    User clicks Book on a zone.
    Creates a PENDING_PAYMENT booking with auto-assigned slot.
    Booking created BEFORE payment to prevent double-booking.
    """
    from django.db import transaction as db_transaction

    plate_number = request.data.get('plate_number', '').upper().strip()
    booking_date = request.data.get('date')
    start_time = request.data.get('start_time')
    end_time = request.data.get('end_time')
    zone_name = request.data.get('zone_name')
    duration_minutes = int(request.data.get('duration_minutes', 60))

    # WRONG — never do this:
    # user = get_default_user()

    # CORRECT — always use request.user:
    if not request.user.is_authenticated:
        return Response({'error': 'Login required to make a booking'}, status=401)

    user = request.user

    # Verify vehicle belongs to this user
    vehicle, created = Vehicle.objects.get_or_create(
        vehicle_no=plate_number,
        defaults={
            'owner_name': user.username,
            'vehicle_type': 'Compact',
            'registered_user': user
        }
    )

    # If vehicle exists but belongs to someone else, still allow
    # (walk-in vehicles won't have registered_user)

    if not all([plate_number, booking_date, start_time, end_time, zone_name]):
        return Response({'error': 'All fields required'}, status=400)

    try:
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(start_time, '%H:%M').time()
        end_time_obj = datetime.strptime(end_time, '%H:%M').time()
    except ValueError:
        return Response({'error': 'Invalid date/time format'}, status=400)

    duration_hours = duration_minutes / 60
    booking_amount = max(20, round(duration_hours * BOOKING_RATE))

    try:
        with db_transaction.atomic():
            # Find and lock an available slot in the zone
            blocked_slots = Booking.objects.filter(
                booking_date=booking_date_obj,
                status__in=['CONFIRMED', 'ACTIVE', 'PENDING_PAYMENT'],
                booking_paid=True,
                start_time__lt=end_time_obj,
                end_time__gt=start_time_obj
            ).values_list('slot_id', flat=True)

            # Row-level lock to prevent race condition
            slot = ParkingSlot.objects.select_for_update().filter(
                is_active=True,
                zone_name=zone_name
            ).exclude(slot_id__in=blocked_slots).first()

            if not slot:
                return Response({
                    'error': f'No slots available in {zone_name} for this time window. '
                              'Please try another zone or time.'
                }, status=400)

            # Get or create vehicle
            vehicle, _ = Vehicle.objects.get_or_create(
                vehicle_no=plate_number,
                defaults={'owner_name': 'User', 'vehicle_type': 'Compact'}
            )

            user = request.user if request.user.is_authenticated else get_default_user()

            # Create booking as PENDING_PAYMENT BEFORE payment
            booking = Booking.objects.create(
                user=user,
                vehicle=vehicle,
                slot=slot,
                booking_date=booking_date_obj,
                start_time=start_time_obj,
                end_time=end_time_obj,
                status='PENDING_PAYMENT',
                booking_amount=booking_amount,
                booking_paid=False
            )

        return Response({
            'success': True,
            'booking_id': booking.id,
            'zone_name': zone_name,
            'date': booking_date,
            'start_time': start_time,
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'booking_amount': booking_amount,
            'plate_number': plate_number,
            'message': f'Slot reserved in {zone_name}. Complete payment to confirm.'
        })

    except Exception as e:
        return Response({'error': str(e)}, status=500)



@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_booking_payment(request):
    """
    After Razorpay payment — verify and confirm booking.
    """
    import razorpay
    import hmac
    import hashlib
    from django.conf import settings

    razorpay_order_id = request.data.get('razorpay_order_id')
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    razorpay_signature = request.data.get('razorpay_signature')
    booking_id = request.data.get('booking_id')

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, booking_id]):
        return Response({'error': 'Missing payment fields'}, status=400)

    # Verify signature
    key_secret = settings.RAZORPAY_KEY_SECRET.encode('utf-8')
    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
    generated_sig = hmac.new(key_secret, message, hashlib.sha256).hexdigest()

    if generated_sig != razorpay_signature:
        return Response({'error': 'Payment verification failed'}, status=400)

    try:
        booking = Booking.objects.get(id=booking_id, status='PENDING_PAYMENT')
        booking.status = 'CONFIRMED'
        booking.booking_paid = True
        booking.booking_payment_id = razorpay_payment_id
        booking.booking_order_id = razorpay_order_id
        booking.save()

        # Sync slot statuses
        sync_slot_statuses()

        return Response({
            'success': True,
            'booking_id': booking.id,
            'zone_name': booking.slot.zone_name,
            'date': str(booking.booking_date),
            'start_time': str(booking.start_time)[:5],
            'end_time': str(booking.end_time)[:5],
            'booking_amount_paid': f'₹{booking.booking_amount}',
            'message': 'Booking confirmed successfully!'
        })

    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found or already confirmed'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_bookings(request):
    """Returns only the logged-in user's bookings."""
    bookings = Booking.objects.filter(
        user=request.user
    ).order_by('-created_at')
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)