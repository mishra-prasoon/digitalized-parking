from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction', 'amount_paise', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('razorpay_order_id', 'razorpay_payment_id')
