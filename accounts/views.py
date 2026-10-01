from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone
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

    from core.models import ParkingSlot
    from parking.models import Transaction
    from payments.models import Payment

    slots = ParkingSlot.objects.all().order_by('slot_id')
    today = timezone.now().date()
    today_revenue = Payment.objects.filter(status='paid', created_at__date=today).aggregate(total=Sum('amount_paise'))['total'] or 0
    active_count = Transaction.objects.exclude(status='closed').count()

    return render(request, 'dashboard/home.html', {
        'slots': slots,
        'today_revenue_rupees': today_revenue / 100,
        'active_count': active_count,
        'total_slots': slots.count(),
    })
