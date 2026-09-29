from django.contrib.auth.decorators import login_not_required
from django.urls import path

from . import views

urlpatterns = [
    path('api/anpr/<str:gate>/', login_not_required(views.anpr_read), name='anpr_read'),
]
