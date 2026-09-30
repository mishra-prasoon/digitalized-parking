from django.db import models

from parking.models import Transaction


class Payment(models.Model):
    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'

    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='payment')
    razorpay_order_id = models.CharField(max_length=100)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)
    amount_paise = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Payment for txn {self.transaction_id} ({self.status})'
