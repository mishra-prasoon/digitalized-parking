from django.urls import path
from . import views

urlpatterns = [
    path('entry/', views.vehicle_entry, name='vehicle-entry'),
    path('exit/', views.vehicle_exit, name='vehicle-exit'),
    path('list/', views.transaction_list, name='transaction-list'),
    path('active/', views.active_transactions, name='active-transactions'),
    path('anpr-process/', views.anpr_from_image, name='anpr-process'),
]