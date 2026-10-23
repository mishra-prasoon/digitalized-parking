from django.contrib import admin, messages

from .models import Tariff, Transaction


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ('hourly_rate', 'min_charge', 'is_active')


@admin.action(description='Force free slot (close transaction without payment)')
def force_close_transaction(modeladmin, request, queryset):
    to_close = queryset.exclude(status=Transaction.Status.CLOSED)
    count = to_close.count()
    to_close.update(status=Transaction.Status.CLOSED)
    if count:
        modeladmin.message_user(
            request,
            f'{count} transaction(s) force-closed and slot(s) freed.',
            level=messages.SUCCESS,
        )
    else:
        modeladmin.message_user(
            request,
            'Selected transaction(s) were already closed.',
            level=messages.INFO,
        )


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'vehicle', 'slot', 'entry_time', 'exit_time', 'status', 'fee')
    list_filter = ('status',)
    search_fields = ('vehicle__plate', 'slot__slot_id')
    actions = [force_close_transaction]
