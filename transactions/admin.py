from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'vehicle', 'slot', 'entry_time', 'exit_time', 'total_fee', 'payment_status']
    list_filter = ['payment_status']
    search_fields = ['vehicle__vehicle_no']