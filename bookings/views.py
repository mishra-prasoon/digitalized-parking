from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime

from slots.models import ParkingSlot
from vehicles.models import Vehicle
from .models import Booking
from .serializers import BookingSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def create_booking(request):
    """
    Create advance slot pre-booking.
    Expects: {
        "plate_number": "UP32AB1234",
        "booking_date": "2026-08-16",
        "start_time": "10:00",
        "end_time": "13:00",
        "zone_name": "Ground Floor",
        "slot_type": "Compact"
    }
    """
    plate_number = request.data.get('plate_number', '').upper().strip()
    booking_date = request.data.get('booking_date')
    start_time = request.data.get('start_time')
    end_time = request.data.get('end_time')
    zone_name = request.data.get('zone_name', '')
    slot_type = request.data.get('slot_type', 'Compact')

    # Validate required fields
    if not all([plate_number, booking_date, start_time, end_time]):
        return Response({'error': 'plate_number, booking_date, start_time, end_time are required'}, status=400)

    # Parse date and times
    try:
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(start_time, '%H:%M').time()
        end_time_obj = datetime.strptime(end_time, '%H:%M').time()
    except ValueError:
        return Response({'error': 'Invalid date/time format. Use YYYY-MM-DD and HH:MM'}, status=400)

    # Date must not be in the past
    if booking_date_obj < timezone.now().date():
        return Response({'error': 'Booking date cannot be in the past'}, status=400)

    # Start time must be before end time
    if start_time_obj >= end_time_obj:
        return Response({'error': 'Start time must be before end time'}, status=400)

    # Get or create vehicle
    vehicle, _ = Vehicle.objects.get_or_create(
        vehicle_no=plate_number,
        defaults={'owner_name': 'Registered User', 'vehicle_type': slot_type}
    )

    # Find available slots — check for overlap
    # A slot is available if no booking exists for same date where:
    # existing_start < requested_end AND existing_end > requested_start
    conflicting_slots = Booking.objects.filter(
        booking_date=booking_date_obj,
        status__in=['CONFIRMED', 'ACTIVE'],
        start_time__lt=end_time_obj,
        end_time__gt=start_time_obj
    ).values_list('slot_id', flat=True)

    # Find slots not in conflict
    available_slots = ParkingSlot.objects.filter(
        is_active=True,
        slot_type=slot_type
    ).exclude(slot_id__in=conflicting_slots)

    if zone_name:
        available_slots = available_slots.filter(zone_name=zone_name)

    if not available_slots.exists():
        return Response({
            'error': 'No slots available for the selected date, time and preferences'
        }, status=400)

    # Assign first available slot
    slot = available_slots.first()

    # Create booking
    booking = Booking.objects.create(
        user=request.user if request.user.is_authenticated else get_default_user(),
        vehicle=vehicle,
        slot=slot,
        booking_date=booking_date_obj,
        start_time=start_time_obj,
        end_time=end_time_obj,
        status='CONFIRMED'
    )

    return Response({
        'success': True,
        'message': f'Slot {slot.slot_id} booked successfully!',
        'booking_id': booking.id,
        'slot_id': slot.slot_id,
        'zone': slot.zone_name,
        'slot_type': slot.slot_type,
        'plate_number': plate_number,
        'booking_date': booking_date,
        'start_time': start_time,
        'end_time': end_time,
        'status': 'CONFIRMED'
    }, status=201)


def get_default_user():
    from django.contrib.auth.models import User
    return User.objects.filter(is_superuser=True).first()


@api_view(['GET'])
@permission_classes([AllowAny])
def booking_list(request):
    bookings = Booking.objects.all().order_by('-created_at')
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def cancel_booking(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
        if booking.status in ['COMPLETED', 'CANCELLED']:
            return Response({'error': f'Booking is already {booking.status}'}, status=400)
        booking.status = 'CANCELLED'
        booking.save()
        return Response({'success': True, 'message': f'Booking {booking_id} cancelled successfully'})
    except Booking.DoesNotExist:
        return Response({'error': 'Booking not found'}, status=404)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_availability(request):
    """
    Check slot availability for a given date and time range.
    Query params: booking_date, start_time, end_time, slot_type, zone_name
    """
    booking_date = request.query_params.get('booking_date')
    start_time = request.query_params.get('start_time')
    end_time = request.query_params.get('end_time')
    slot_type = request.query_params.get('slot_type', '')
    zone_name = request.query_params.get('zone_name', '')

    if not all([booking_date, start_time, end_time]):
        return Response({'error': 'booking_date, start_time, end_time are required'}, status=400)

    try:
        booking_date_obj = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_time_obj = datetime.strptime(start_time, '%H:%M').time()
        end_time_obj = datetime.strptime(end_time, '%H:%M').time()
    except ValueError:
        return Response({'error': 'Invalid format'}, status=400)

    conflicting_slots = Booking.objects.filter(
        booking_date=booking_date_obj,
        status__in=['CONFIRMED', 'ACTIVE'],
        start_time__lt=end_time_obj,
        end_time__gt=start_time_obj
    ).values_list('slot_id', flat=True)

    available = ParkingSlot.objects.filter(is_active=True).exclude(slot_id__in=conflicting_slots)

    if slot_type:
        available = available.filter(slot_type=slot_type)
    if zone_name:
        available = available.filter(zone_name=zone_name)

    from slots.serializers import ParkingSlotSerializer
    return Response({
        'available_count': available.count(),
        'slots': ParkingSlotSerializer(available, many=True).data
    })