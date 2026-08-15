from django.db import models

class ParkingSlot(models.Model):
    SLOT_TYPE_CHOICES = [
        ('Compact', 'Compact'),
        ('SUV', 'SUV'),
    ]
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('booked', 'Booked'),
        ('maintenance', 'Maintenance'),
    ]

    slot_id = models.CharField(max_length=10, primary_key=True)
    zone_name = models.CharField(max_length=50)
    slot_type = models.CharField(max_length=10, choices=SLOT_TYPE_CHOICES, default='Compact')
    is_occupied = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.slot_id} - {self.zone_name} - {self.status}"

    class Meta:
        ordering = ['slot_id']