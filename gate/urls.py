from django.urls import path

from . import views

urlpatterns = [
    path('gate/entry/', views.entry_gate, name='entry_gate'),
    path('gate/entry/check-in/', views.entry_check_in, name='entry_check_in'),
    path('gate/exit/', views.exit_gate, name='exit_gate'),
    path('gate/exit/scan/', views.exit_scan, name='exit_scan'),
    path('gate/exit/confirm/', views.exit_confirm_payment, name='exit_confirm_payment'),
]
