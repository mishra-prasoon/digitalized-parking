import razorpay
import hmac
import hashlib
import json

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from transactions.models import Transaction
from slots.models import ParkingSlot

# Initialize Razorpay client
client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_order(request):
    """
    Create a Razorpay order for parking fee payment.
    Expects: { "transaction_id": 1 }
    """
    transaction_id = request.data.get('transaction_id')

    if not transaction_id:
        return Response({'error': 'transaction_id is required'}, status=400)

    try:
        trans = Transaction.objects.get(id=transaction_id)
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=404)

    if trans.payment_status == 'PAID':
        return Response({'error': 'Payment already completed'}, status=400)

    # Amount in paise (1 INR = 100 paise)
    amount_paise = int(float(trans.total_fee) * 100)

    # Minimum 100 paise (₹1)
    if amount_paise < 100:
        amount_paise = 100

    try:
        # Create Razorpay order
        order_data = {
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': f'parking_tx_{transaction_id}',
            'notes': {
                'transaction_id': str(transaction_id),
                'vehicle': str(trans.vehicle.vehicle_no),
                'slot': str(trans.slot.slot_id)
            }
        }
        razorpay_order = client.order.create(data=order_data)

        # Save order ID to transaction
        trans.razorpay_order_id = razorpay_order['id']
        trans.save()

        return Response({
            'success': True,
            'order_id': razorpay_order['id'],
            'amount': amount_paise,
            'amount_inr': float(trans.total_fee),
            'currency': 'INR',
            'key_id': settings.RAZORPAY_KEY_ID,
            'vehicle_no': trans.vehicle.vehicle_no,
            'slot_id': trans.slot.slot_id,
            'transaction_id': transaction_id
        })

    except Exception as e:
        return Response({'error': f'Razorpay error: {str(e)}'}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_payment(request):
    """
    Verify Razorpay payment signature and complete the transaction.
    Expects: {
        "razorpay_order_id": "...",
        "razorpay_payment_id": "...",
        "razorpay_signature": "...",
        "transaction_id": 1
    }
    """
    razorpay_order_id = request.data.get('razorpay_order_id')
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    razorpay_signature = request.data.get('razorpay_signature')
    transaction_id = request.data.get('transaction_id')

    # Validate all fields present
    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, transaction_id]):
        return Response({'error': 'Missing required payment fields'}, status=400)

    # Verify signature using HMAC-SHA256
    key_secret = settings.RAZORPAY_KEY_SECRET.encode('utf-8')
    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
    generated_signature = hmac.new(key_secret, message, hashlib.sha256).hexdigest()

    if generated_signature != razorpay_signature:
        return Response({'error': 'Payment signature verification failed'}, status=400)

    # Signature verified — update transaction
    try:
        trans = Transaction.objects.get(id=transaction_id)

        trans.razorpay_payment_id = razorpay_payment_id
        trans.payment_status = 'PAID'
        trans.save()

        # Free the parking slot
        slot = trans.slot
        slot.is_occupied = False
        slot.status = 'available'
        slot.save()

        return Response({
            'success': True,
            'message': f'Payment successful! Slot {slot.slot_id} is now free.',
            'transaction_id': transaction_id,
            'payment_id': razorpay_payment_id,
            'slot_id': slot.slot_id,
            'amount_paid': f'₹{trans.total_fee}'
        })

    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def payment_failed(request):
    """Handle failed payment — still free the slot so parking lot doesn't get stuck."""
    transaction_id = request.data.get('transaction_id')
    try:
        trans = Transaction.objects.get(id=transaction_id)
        trans.payment_status = 'FAILED'
        trans.save()

        # Free the slot anyway so parking lot doesn't get stuck
        slot = trans.slot
        slot.is_occupied = False
        slot.status = 'available'
        slot.save()

        return Response({'message': 'Payment failure recorded, slot freed'})
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=404)