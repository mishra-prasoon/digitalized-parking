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
    'total_fee': total_fee,
    'total_fee_display': f'₹{total_fee}',
    'payment_status': 'PENDING',
    'payment_url': f'/payment/?transaction_id={trans.id}&vehicle={plate_number}&slot={trans.slot.slot_id}&fee={total_fee}&duration={duration_hours}'
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

@api_view(['POST'])
@permission_classes([AllowAny])
def anpr_from_image(request):
    """
    Receives an image, runs ANPR, returns detected plate number.
    Then processes entry or exit based on gate_type.
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'anpr'))

    gate_type = request.data.get('gate_type', 'entry')
    image_file = request.FILES.get('image')

    if not image_file:
        return Response({'error': 'No image provided'}, status=400)

    try:
        import cv2
        import pytesseract
        import numpy as np
        import re

        pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'

        # Read image from upload
        img_array = np.frombuffer(image_file.read(), np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if image is None:
            return Response({'error': 'Could not process image'}, status=400)

        # Preprocess
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        filtered = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(filtered, 30, 200)

        # Find plate contour
        contours, _ = cv2.findContours(edges.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:30]

        plate_text = None
        for contour in contours:
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                cropped = gray[y:y+h, x:x+w]
                _, thresh = cv2.threshold(cropped, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                config = '--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                raw = pytesseract.image_to_string(thresh, config=config)
                cleaned = re.sub(r'[^A-Z0-9]', '', raw.upper().strip())
                if len(cleaned) >= 6:
                    plate_text = cleaned
                    break

        # Fallback — full image OCR
        if not plate_text:
            config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            raw = pytesseract.image_to_string(gray, config=config)
            cleaned = re.sub(r'[^A-Z0-9]', '', raw.upper().strip())
            if len(cleaned) >= 6:
                plate_text = cleaned

        if not plate_text:
            return Response({
                'success': False,
                'error': 'Could not detect plate number. Please try a clearer image.'
            }, status=400)

        # Now process entry or exit
        from vehicles.models import Vehicle
        from slots.models import ParkingSlot
        from bookings.models import Booking
        from .models import Transaction
        from django.utils import timezone
        from django.db import transaction as db_transaction
        import math

        if gate_type == 'entry':
            # Check duplicate
            open_tx = Transaction.objects.filter(
                vehicle__vehicle_no=plate_text,
                exit_time__isnull=True
            ).first()

            if open_tx:
                return Response({
                    'success': False,
                    'plate_detected': plate_text,
                    'error': f'Vehicle {plate_text} already parked in slot {open_tx.slot.slot_id}'
                }, status=400)

            vehicle, _ = Vehicle.objects.get_or_create(
                vehicle_no=plate_text,
                defaults={'owner_name': 'Walk-in', 'vehicle_type': 'Compact'}
            )

            # Check pre-booking
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
                    slot = active_booking.slot
                    active_booking.status = 'ACTIVE'
                    active_booking.save()
                    entry_type = 'PRE-BOOKED'
                else:
                    slot = ParkingSlot.objects.select_for_update().filter(
                        is_occupied=False, is_active=True, status='available'
                    ).first()
                    if not slot:
                        return Response({
                            'success': False,
                            'plate_detected': plate_text,
                            'error': 'Parking lot is full'
                        }, status=400)
                    entry_type = 'WALK-IN'

                slot.is_occupied = True
                slot.status = 'occupied'
                slot.save()
                trans = Transaction.objects.create(vehicle=vehicle, slot=slot, booking=active_booking)

            return Response({
                'success': True,
                'plate_detected': plate_text,
                'gate_type': 'ENTRY',
                'entry_type': entry_type,
                'message': f'Welcome! {plate_text} → Slot {slot.slot_id}',
                'slot_id': slot.slot_id,
                'zone': slot.zone_name,
                'transaction_id': trans.id,
                'entry_time': trans.entry_time
            })

        else:  # exit
            try:
                trans = Transaction.objects.get(
                    vehicle__vehicle_no=plate_text,
                    exit_time__isnull=True
                )
            except Transaction.DoesNotExist:
                return Response({
                    'success': False,
                    'plate_detected': plate_text,
                    'error': f'No active transaction for {plate_text}'
                }, status=404)

            exit_time = timezone.now()
            duration = exit_time - trans.entry_time
            hours = max(1, math.ceil(duration.total_seconds() / 3600))
            fee = hours * 50

            trans.exit_time = exit_time
            trans.total_fee = fee
            trans.save()

            trans.slot.is_occupied = False
            trans.slot.status = 'available'
            trans.slot.save()

            return Response({
                'success': True,
                'plate_detected': plate_text,
                'gate_type': 'EXIT',
                'message': f'Goodbye! {plate_text} — Fee: ₹{fee}',
                'slot_id': trans.slot.slot_id,
                'duration_hours': hours,
                'total_fee': f'₹{fee}',
                'transaction_id': trans.id
            })

    except Exception as e:
        return Response({'error': str(e)}, status=500)