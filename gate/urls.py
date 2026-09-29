from django.urls import path

from . import views

urlpatterns = [
    path('gate/entry/', views.entry_gate, name='entry_gate'),
    path('gate/entry/check-in/', views.entry_check_in, name='entry_check_in'),
]
