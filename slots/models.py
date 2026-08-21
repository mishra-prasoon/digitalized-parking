from django.db import models

class ParkingSlot(models.Model):
    SLOT_TYPE_CHOICES = [
        ('Compact', 'Compact'),
        ('SUV', 'SUV'),
    ]

    slot_id = models.CharField(max_length=10, primary_key=True)
    zone_name = models.CharField(max_length=50)
    slot_type = models.CharField(
        max_length=10, choices=SLOT_TYPE_CHOICES, default='Compact'
    )
    is_occupied = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def status(self):
        if not self.is_active:
            return 'inactive'
        return 'occupied' if self.is_occupied else 'available'

    def __str__(self):
        return f"{self.slot_id} - {self.zone_name} - {self.status}"

    class Meta:
        ordering = ['slot_id']