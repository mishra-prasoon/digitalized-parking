from datetime import timedelta

from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Count, F, ExpressionWrapper, DurationField
from django.db.models.functions import TruncDate, ExtractHour
from django.shortcuts import render
from django.utils import timezone

from core.models import ParkingSlot
from parking.models import Transaction
from payments.models import Payment


def reports_home(request):
    if not request.user.is_staff_member:
        raise PermissionDenied

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    # 1. Daily Occupancy Report (last 7 days)
    entries_by_day = (
        Transaction.objects.filter(entry_time__gte=week_ago)
        .annotate(day=TruncDate('entry_time'))
        .values('day')
        .annotate(entered=Count('id'))
        .order_by('day')
    )
    exits_by_day = (
        Transaction.objects.filter(exit_time__gte=week_ago, exit_time__isnull=False)
        .annotate(day=TruncDate('exit_time'))
        .values('day')
        .annotate(exited=Count('id'))
        .order_by('day')
    )
    exits_map = {row['day']: row['exited'] for row in exits_by_day}
    daily_occupancy = [
        {'day': row['day'], 'entered': row['entered'], 'exited': exits_map.get(row['day'], 0)}
        for row in entries_by_day
    ]
    currently_parked = Transaction.objects.exclude(status=Transaction.Status.CLOSED).count()

    # 2. Revenue Report (last 7 days, by day)
    revenue_by_day = (
        Payment.objects.filter(status='paid', created_at__gte=week_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total_paise=Sum('amount_paise'))
        .order_by('day')
    )
    revenue_rows = [
        {'day': row['day'], 'total_rupees': row['total_paise'] / 100}
        for row in revenue_by_day
    ]
    week_total_paise = Payment.objects.filter(status='paid', created_at__gte=week_ago).aggregate(
        t=Sum('amount_paise'))['t'] or 0

    context = {
        'daily_occupancy': daily_occupancy,
        'currently_parked': currently_parked,
        'revenue_rows': revenue_rows,
        'week_total_rupees': week_total_paise / 100,
    }
    context = _add_peak_hours_transaction_log_and_utilization(context, now, week_ago)
    return render(request, 'dashboard/reports.html', context)


def _add_peak_hours_transaction_log_and_utilization(context, now, week_ago):
    # 3. Peak Hours Report (entries by hour of day, last 7 days)
    entries = Transaction.objects.filter(entry_time__gte=week_ago)
    hour_counts = {h: 0 for h in range(24)}
    for t in entries.annotate(hour=ExtractHour('entry_time')).values('hour').annotate(c=Count('id')):
        hour_counts[t['hour']] = t['c']
    peak_hours = [{'hour': h, 'count': hour_counts[h]} for h in range(24)]
    busiest_hour = max(peak_hours, key=lambda x: x['count']) if any(p['count'] for p in peak_hours) else None

    # 4. Transaction Log (most recent 25)
    recent_transactions = (
        Transaction.objects.select_related('vehicle', 'slot')
        .order_by('-entry_time')[:25]
    )

    # 5. Slot Utilization Report (% of last 7 days each slot was occupied, approx by session count/hours)
    slots = ParkingSlot.objects.all().order_by('slot_id')
    utilization = []
    for slot in slots:
        sessions = Transaction.objects.filter(slot=slot, entry_time__gte=week_ago)
        total_hours = 0
        for t in sessions:
            end = t.exit_time or now
            total_hours += (end - t.entry_time).total_seconds() / 3600
        possible_hours = 7 * 24
        pct = round((total_hours / possible_hours) * 100, 1) if possible_hours else 0
        utilization.append({
            'slot_id': slot.slot_id,
            'zone': slot.zone_name,
            'sessions': sessions.count(),
            'hours_used': round(total_hours, 1),
            'utilization_pct': min(pct, 100),
        })

    context.update({
        'peak_hours': peak_hours,
        'busiest_hour': busiest_hour,
        'recent_transactions': recent_transactions,
        'utilization': utilization,
    })
    return context
