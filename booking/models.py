from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import ParkingSlot, Vehicle


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='bookings')
    slot = models.ForeignKey(ParkingSlot, on_delete=models.CASCADE, related_name='bookings')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        errors = {}

        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                errors['end_time'] = 'End time must be after start time.'
            elif self.start_time < timezone.now() + timezone.timedelta(minutes=10):
                errors['start_time'] = 'Booking must start at least 10 minutes from now.'
            elif self.end_time - self.start_time > timezone.timedelta(hours=24):
                errors['end_time'] = 'Booking cannot be longer than 24 hours.'

        if errors:
            raise ValidationError(errors)

        if self.slot_id and self.start_time and self.end_time and self.status == self.Status.CONFIRMED:
            conflicts = Booking.objects.filter(
                slot_id=self.slot_id,
                status=self.Status.CONFIRMED,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).exclude(pk=self.pk)
            if conflicts.exists():
                raise ValidationError('This slot is already booked for an overlapping time.')

    def __str__(self):
        return f'{self.vehicle_id} @ {self.slot_id} ({self.start_time:%Y-%m-%d %H:%M})'
