from django.db import models
from django.conf import settings
from slots.models import ParkingSlot
from vehicles.models import Vehicle

class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING_PAYMENT', 'Pending Payment'),
        ('CONFIRMED', 'Confirmed'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('NO_SHOW', 'No Show'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name='bookings'
    )
    slot = models.ForeignKey(
        ParkingSlot, on_delete=models.CASCADE, related_name='bookings'
    )
    booking_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDING_PAYMENT'
    )
    booking_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    booking_payment_id = models.CharField(max_length=100, blank=True, null=True)
    booking_order_id = models.CharField(max_length=100, blank=True, null=True)
    booking_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking {self.id} - {self.vehicle} - {self.slot} - {self.status}"

    class Meta:
        ordering = ['-created_at']

    def duration_hours(self):
        from datetime import datetime, date
        start = datetime.combine(date.today(), self.start_time)
        end = datetime.combine(date.today(), self.end_time)
        diff = (end - start).total_seconds() / 3600
        return max(1, round(diff))