from django.urls import path
from . import views

urlpatterns = [
    path('entry/', views.entry_display, name='entry-display'),
    path('exit/', views.exit_kiosk, name='exit-kiosk'),
]