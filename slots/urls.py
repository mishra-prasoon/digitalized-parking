from django.urls import path
from . import views

urlpatterns = [
    path('', views.SlotListView.as_view(), name='slot-list'),
    path('available/', views.available_slots, name='available-slots'),
    path('<str:slot_id>/update/', views.update_slot_status, name='update-slot'),
]