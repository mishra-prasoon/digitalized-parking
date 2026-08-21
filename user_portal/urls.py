from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('slots/', views.slots_view, name='slots'),
    path('book/', views.book_view, name='book'),
    path('my-bookings/', views.my_bookings, name='my-bookings'),
    path('payment/', views.payment_view, name='payment'),
    path('anpr-demo/', views.anpr_demo, name='anpr-demo'),
]