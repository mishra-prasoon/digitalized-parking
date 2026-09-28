from django.db import models

from core.models import ParkingSlot, Vehicle
from booking.models import Booking


class Tariff(models.Model):
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, default=20)
    min_charge = models.DecimalField(max_digits=8, decimal_places=2, default=20)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'₹{self.hourly_rate}/hr (min ₹{self.min_charge})'


class Transaction(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        AWAITING_PAYMENT = 'awaiting_payment', 'Awaiting Payment'
        CLOSED = 'closed', 'Closed'

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='transactions')
    slot = models.ForeignKey(ParkingSlot, on_delete=models.CASCADE, related_name='transactions')
    booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions')
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    def __str__(self):
        return f'{self.vehicle_id} @ {self.slot_id} ({self.status})'
