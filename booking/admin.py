from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'vehicle', 'slot', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'slot')
    search_fields = ('user__username', 'vehicle__plate', 'slot__slot_id')
