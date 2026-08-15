from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('slots/', views.slots_view, name='slots'),
    path('book/', views.book_view, name='book'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
]