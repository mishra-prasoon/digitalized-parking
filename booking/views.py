from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.urls import reverse
from urllib.parse import urlencode

from core.models import ParkingSlot, Vehicle
from .forms import AvailabilityForm, VehicleForm
from .models import Booking


def _parse_local(dt_str):
    dt = parse_datetime(dt_str) if dt_str else None
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def create_booking(request):
    """Step 1: pick a vehicle and a time window, then check availability."""
    if request.method == 'POST':
        form = AvailabilityForm(request.POST, user=request.user)
        if form.is_valid():
            v = form.cleaned_data['vehicle']
            start = form.cleaned_data['start_time']
            end = form.cleaned_data['end_time']
            query = urlencode({
                'vehicle': v.plate,
                'start': start.isoformat(),
                'end': end.isoformat(),
            })
            url = reverse('select_slot') + '?' + query
            return redirect(url)
    else:
        form = AvailabilityForm(user=request.user)

    has_vehicle = Vehicle.objects.filter(owner=request.user).exists()
    return render(request, 'booking/create.html', {'form': form, 'has_vehicle': has_vehicle})


def select_slot(request):
    """Step 2: show every active slot free for the chosen window."""
    vehicle = get_object_or_404(Vehicle, plate=request.GET.get('vehicle'), owner=request.user)
    start = _parse_local(request.GET.get('start'))
    end = _parse_local(request.GET.get('end'))

    if not start or not end or start >= end:
        messages.error(request, 'Please choose a valid start and end time.')
        return redirect('create_booking')

    conflicting_slot_ids = Booking.objects.filter(
        status=Booking.Status.CONFIRMED,
        start_time__lt=end,
        end_time__gt=start,
    ).values_list('slot_id', flat=True)

    available_slots = (
        ParkingSlot.objects.filter(is_active=True)
        .exclude(slot_id__in=conflicting_slot_ids)
        .order_by('slot_id')
    )

    return render(request, 'booking/select_slot.html', {
        'vehicle': vehicle,
        'start': start,
        'end': end,
        'slots': available_slots,
    })


def confirm_slot_booking(request):
    """Step 3: create the booking for the chosen slot."""
    if request.method != 'POST':
        return redirect('create_booking')

    vehicle = get_object_or_404(Vehicle, plate=request.POST.get('vehicle'), owner=request.user)
    slot = get_object_or_404(ParkingSlot, pk=request.POST.get('slot'))
    start = _parse_local(request.POST.get('start'))
    end = _parse_local(request.POST.get('end'))

    booking = Booking(user=request.user, vehicle=vehicle, slot=slot, start_time=start, end_time=end)
    try:
        booking.full_clean()
        booking.save()
        messages.success(request, f'Booking confirmed for slot {slot.slot_id}.')
        return redirect('my_bookings')
    except ValidationError as e:
        detail = '; '.join(e.messages) if hasattr(e, 'messages') else str(e)
        messages.error(request, f'Could not confirm booking: {detail}')
        return redirect('create_booking')


def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-start_time')
    return render(request, 'booking/list.html', {'bookings': bookings})


def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if request.method == 'POST' and booking.status == Booking.Status.CONFIRMED:
        booking.status = Booking.Status.CANCELLED
        booking.save()
        messages.success(request, 'Booking cancelled.')
    return redirect('my_bookings')


def add_vehicle(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.owner = request.user
            vehicle.save()
            messages.success(request, f'Vehicle {vehicle.plate} added.')
            return redirect('create_booking')
    else:
        form = VehicleForm()
    return render(request, 'booking/add_vehicle.html', {'form': form})
