from django.contrib import admin
from .models import ParkingSlot

@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ['slot_id', 'zone_name', 'slot_type', 'status', 'is_occupied', 'is_active']
    list_filter = ['zone_name', 'slot_type', 'status']
    search_fields = ['slot_id', 'zone_name']