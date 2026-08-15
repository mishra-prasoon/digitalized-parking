from django.contrib import admin
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'vehicle', 'slot', 'booking_date', 'start_time', 'end_time', 'status']
    list_filter = ['status', 'booking_date']
    search_fields = ['vehicle__vehicle_no']