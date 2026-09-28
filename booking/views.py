from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import BookingForm
from .models import Booking


def create_booking(request):
    if request.method == 'POST':
        form = BookingForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Booking confirmed.')
                return redirect('my_bookings')
            except ValidationError as e:
                form.add_error(None, e)
    else:
        form = BookingForm(user=request.user)
    return render(request, 'booking/create.html', {'form': form})


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
