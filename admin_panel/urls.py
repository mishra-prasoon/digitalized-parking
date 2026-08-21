from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='admin-dashboard'),
    path('login/', views.login_view, name='admin-login'),
    path('logout/', views.logout_view, name='admin-logout'),
    path('slots/', views.slots_view, name='admin-slots'),
    path('slots/add/', views.add_slot, name='add-slot'),
    path('slots/delete/<str:slot_id>/', views.delete_slot, name='delete-slot'),
    path('transactions/', views.transactions_view, name='admin-transactions'),
    path('reports/', views.reports_view, name='admin-reports'),
    path('gate-control/', views.gate_control, name='gate-control'),
    path('slot/<str:slot_id>/override/', views.override_slot, name='override-slot'),
]