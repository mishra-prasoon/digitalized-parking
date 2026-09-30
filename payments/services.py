import razorpay
from django.conf import settings

from parking.models import Transaction
from parking.services import close_transaction
from .models import Payment


class PaymentError(Exception):
    pass


def _client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_order(transaction):
    if transaction.status != Transaction.Status.AWAITING_PAYMENT:
        raise PaymentError('Transaction is not awaiting payment.')

    amount_paise = int(transaction.fee * 100)
    client = _client()
    order = client.order.create({
        'amount': amount_paise,
        'currency': 'INR',
        'receipt': f'txn-{transaction.id}',
        'payment_capture': 1,
    })

    payment, _ = Payment.objects.update_or_create(
        transaction=transaction,
        defaults={
            'razorpay_order_id': order['id'],
            'amount_paise': amount_paise,
            'status': Payment.Status.CREATED,
        },
    )
    return payment, order


def verify_and_close(transaction, razorpay_order_id, razorpay_payment_id, razorpay_signature):
    try:
        payment = transaction.payment
    except Payment.DoesNotExist:
        raise PaymentError('No payment record found for this transaction.')

    if transaction.status == Transaction.Status.CLOSED:
        return payment  # already closed; safe no-op

    if payment.razorpay_order_id != razorpay_order_id:
        raise PaymentError('Order ID mismatch.')

    client = _client()
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        payment.status = Payment.Status.FAILED
        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.save()
        raise PaymentError('Payment signature verification failed.')

    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.status = Payment.Status.PAID
    payment.save()

    close_transaction(transaction)
    return payment
