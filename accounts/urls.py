from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import path

from . import views, reports_views

urlpatterns = [
    path('register/', login_not_required(views.RegisterView.as_view()), name='register'),
    path('login/', login_not_required(auth_views.LoginView.as_view(template_name='accounts/login.html')), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('redirect/', views.dashboard_redirect, name='dashboard_redirect'),
    path('portal/', views.portal_home, name='user_portal'),
    path('dashboard/', views.staff_dashboard_home, name='staff_dashboard'),
    path('dashboard/reports/', reports_views.reports_home, name='reports_home'),
]
