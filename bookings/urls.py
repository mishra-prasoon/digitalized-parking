from django.urls import path
from . import views

urlpatterns = [
    path('book/', views.create_booking, name='create-booking'),
    path('bookings/', views.booking_list, name='booking-list'),
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking, name='cancel-booking'),
    path('check-availability/', views.check_availability, name='check-availability'),
]