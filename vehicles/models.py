from django.db import models
from django.contrib.auth.models import User

class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ('Compact', 'Compact'),
        ('SUV', 'SUV'),
    ]

    vehicle_no = models.CharField(max_length=15, primary_key=True)
    owner_name = models.CharField(max_length=100, blank=True, null=True)
    vehicle_type = models.CharField(max_length=10, choices=VEHICLE_TYPE_CHOICES, default='Compact')
    registered_user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vehicles'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vehicle_no} - {self.owner_name}"