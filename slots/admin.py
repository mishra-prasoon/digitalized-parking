from django.contrib import admin
from .models import ParkingSlot

@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ['slot_id', 'zone_name', 'slot_type', 'is_occupied', 'is_active', 'status']
    list_filter = ['zone_name', 'slot_type', 'is_occupied', 'is_active']
    search_fields = ['slot_id', 'zone_name']
    readonly_fields = ['status']