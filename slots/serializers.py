from rest_framework import serializers
from .models import ParkingSlot

class ParkingSlotSerializer(serializers.ModelSerializer):
    status = serializers.ReadOnlyField()

    class Meta:
        model = ParkingSlot
        fields = ['slot_id', 'zone_name', 'slot_type',
                  'is_occupied', 'is_active', 'status', 'created_at']