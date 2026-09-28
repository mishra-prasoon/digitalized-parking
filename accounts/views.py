from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.generic import CreateView

from .forms import RegisterForm


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = 'accounts/register.html'
    success_url = '/portal/'

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


def dashboard_redirect(request):
    if request.user.is_staff_member:
        return redirect('staff_dashboard')
    return redirect('user_portal')


def portal_home(request):
    return render(request, 'portal/home.html')


def staff_dashboard_home(request):
    if not request.user.is_staff_member:
        raise PermissionDenied
    return render(request, 'dashboard/home.html')
