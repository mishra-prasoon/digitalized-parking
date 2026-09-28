from django.urls import path

from . import views

urlpatterns = [
    path('bookings/new/', views.create_booking, name='create_booking'),
    path('bookings/', views.my_bookings, name='my_bookings'),
    path('bookings/<int:pk>/cancel/', views.cancel_booking, name='cancel_booking'),
]
