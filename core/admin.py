from django.contrib import admin

from .models import ParkingSlot, Vehicle


@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ('slot_id', 'zone_name', 'slot_type', 'is_active', 'is_occupied')
    list_filter = ('zone_name', 'slot_type', 'is_active', 'is_occupied')
    search_fields = ('slot_id',)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('plate', 'owner', 'vehicle_type')
    list_filter = ('vehicle_type',)
    search_fields = ('plate',)
