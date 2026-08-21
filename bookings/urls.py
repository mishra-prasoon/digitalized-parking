from django.urls import path
from . import views

urlpatterns = [
    path('book/', views.create_booking, name='create-booking'),
    path('search-slots/', views.search_slots, name='search-slots'),
    path('initiate-booking/', views.initiate_booking, name='initiate-booking'),
    path('booking-order/', views.create_booking_order, name='booking-order'),
    path('confirm-booking/', views.confirm_booking, name='confirm-booking'),
    path('confirm-booking-payment/', views.confirm_booking_payment, name='confirm-booking-payment'),
    path('bookings/', views.booking_list, name='booking-list'),
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking, name='cancel-booking'),
    path('check-availability/', views.check_availability, name='check-availability'),
    path('bookings/me/', views.my_bookings, name='my-bookings'),
]