from django.contrib import admin

from .models import Tariff, Transaction


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ('hourly_rate', 'min_charge', 'is_active')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'vehicle', 'slot', 'entry_time', 'exit_time', 'status', 'fee')
    list_filter = ('status',)
    search_fields = ('vehicle__plate', 'slot__slot_id')
