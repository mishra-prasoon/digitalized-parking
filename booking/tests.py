from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import ParkingSlot, Vehicle
from .models import Booking

CustomUser = get_user_model()


def make_booking(user, vehicle, slot, hours_from_now, duration_hours=1, **kwargs):
    start = timezone.now() + timezone.timedelta(hours=hours_from_now)
    end = start + timezone.timedelta(hours=duration_hours)
    b = Booking(user=user, vehicle=vehicle, slot=slot, start_time=start, end_time=end, **kwargs)
    b.full_clean()
    b.save()
    return b


class BookingOverlapTests(TestCase):
    def setUp(self):
        self.user1 = CustomUser.objects.create_user(username='u1', password='pass12345')
        self.user2 = CustomUser.objects.create_user(username='u2', password='pass12345')
        self.slot = ParkingSlot.objects.create(slot_id='A-101', zone_name='Ground Floor')
        self.slot2 = ParkingSlot.objects.create(slot_id='A-102', zone_name='Ground Floor')
        self.vehicle1 = Vehicle.objects.create(plate='UP65AB1234', owner=self.user1)
        self.vehicle2 = Vehicle.objects.create(plate='DL01XY9999', owner=self.user2)

    def test_overlapping_booking_same_slot_rejected(self):
        make_booking(self.user1, self.vehicle1, self.slot, hours_from_now=1, duration_hours=2)
        with self.assertRaises(ValidationError):
            make_booking(self.user2, self.vehicle2, self.slot, hours_from_now=2, duration_hours=1)

    def test_non_overlapping_booking_same_slot_allowed(self):
        make_booking(self.user1, self.vehicle1, self.slot, hours_from_now=1, duration_hours=1)
        make_booking(self.user2, self.vehicle2, self.slot, hours_from_now=3, duration_hours=1)
        self.assertEqual(Booking.objects.filter(slot=self.slot).count(), 2)

    def test_overlapping_booking_different_slot_allowed(self):
        make_booking(self.user1, self.vehicle1, self.slot, hours_from_now=1, duration_hours=2)
        make_booking(self.user2, self.vehicle2, self.slot2, hours_from_now=1, duration_hours=2)
        self.assertEqual(Booking.objects.count(), 2)

    def test_cancelled_booking_does_not_block_new_one(self):
        b = make_booking(self.user1, self.vehicle1, self.slot, hours_from_now=1, duration_hours=2)
        b.status = Booking.Status.CANCELLED
        b.save()
        make_booking(self.user2, self.vehicle2, self.slot, hours_from_now=1, duration_hours=2)
        self.assertEqual(Booking.objects.filter(slot=self.slot, status=Booking.Status.CONFIRMED).count(), 1)

    def test_too_soon_start_rejected(self):
        with self.assertRaises(ValidationError):
            make_booking(self.user1, self.vehicle1, self.slot, hours_from_now=0, duration_hours=1)

    def test_too_long_duration_rejected(self):
        with self.assertRaises(ValidationError):
            make_booking(self.user1, self.vehicle1, self.slot, hours_from_now=1, duration_hours=25)


class CancelBookingViewTests(TestCase):
    def setUp(self):
        self.user1 = CustomUser.objects.create_user(username='u1', password='pass12345')
        self.user2 = CustomUser.objects.create_user(username='u2', password='pass12345')
        self.slot = ParkingSlot.objects.create(slot_id='A-101', zone_name='Ground Floor')
        self.vehicle1 = Vehicle.objects.create(plate='UP65AB1234', owner=self.user1)
        self.booking = make_booking(self.user1, self.vehicle1, self.slot, hours_from_now=1, duration_hours=1)

    def test_user_cannot_cancel_others_booking(self):
        self.client.login(username='u2', password='pass12345')
        response = self.client.post(reverse('cancel_booking', args=[self.booking.pk]))
        self.assertEqual(response.status_code, 404)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)

    def test_owner_can_cancel_own_booking(self):
        self.client.login(username='u1', password='pass12345')
        response = self.client.post(reverse('cancel_booking', args=[self.booking.pk]))
        self.assertRedirects(response, reverse('my_bookings'))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CANCELLED)
