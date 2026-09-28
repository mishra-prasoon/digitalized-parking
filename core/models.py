from django.conf import settings
from django.db import models


class ParkingSlot(models.Model):
    class SlotType(models.TextChoices):
        COMPACT = 'compact', 'Compact'
        SUV = 'suv', 'SUV'

    slot_id = models.CharField(max_length=10, primary_key=True)
    zone_name = models.CharField(max_length=20)
    slot_type = models.CharField(max_length=10, choices=SlotType.choices, default=SlotType.COMPACT)
    is_active = models.BooleanField(default=True)
    is_occupied = models.BooleanField(default=False)  # temporary; replaced by derived status in Phase 4

    def __str__(self):
        return self.slot_id


class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        COMPACT = 'compact', 'Compact'
        SUV = 'suv', 'SUV'

    plate = models.CharField(max_length=15, primary_key=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    vehicle_type = models.CharField(max_length=10, choices=VehicleType.choices, default=VehicleType.COMPACT)

    def save(self, *args, **kwargs):
        self.plate = self.plate.upper().replace(' ', '')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.plate
