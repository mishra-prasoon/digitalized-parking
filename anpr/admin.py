from django.contrib import admin

from .models import ANPRLog


@admin.register(ANPRLog)
class ANPRLogAdmin(admin.ModelAdmin):
    list_display = ('gate', 'accepted_plate', 'confidence', 'success', 'created_at')
    list_filter = ('gate', 'success')
    search_fields = ('accepted_plate', 'raw_text')
