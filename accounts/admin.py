from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Parking', {'fields': ('role', 'phone_number')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Parking', {'fields': ('role', 'phone_number')}),)
    list_display = ('username', 'email', 'role', 'is_active')