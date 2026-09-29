from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import ParkingSlot, Vehicle
from parking.models import Tariff, Transaction

CustomUser = get_user_model()


class EntryGatePageTests(TestCase):
    def setUp(self):
        self.staff = CustomUser.objects.create_user(username='staff1', password='pass12345', role=CustomUser.Role.STAFF)
        self.user = CustomUser.objects.create_user(username='user1', password='pass12345', role=CustomUser.Role.USER)

    def test_staff_can_access_entry_gate(self):
        self.client.login(username='staff1', password='pass12345')
        response = self.client.get(reverse('entry_gate'))
        self.assertEqual(response.status_code, 200)

    def test_normal_user_blocked(self):
        self.client.login(username='user1', password='pass12345')
        response = self.client.get(reverse('entry_gate'))
        self.assertEqual(response.status_code, 403)


class EntryCheckInTests(TestCase):
    def setUp(self):
        self.staff = CustomUser.objects.create_user(username='staff1', password='pass12345', role=CustomUser.Role.STAFF)
        self.client.login(username='staff1', password='pass12345')
        ParkingSlot.objects.create(slot_id='A-101', zone_name='Ground Floor')
        Tariff.objects.create(hourly_rate=20, min_charge=20, is_active=True)

    def test_manual_entry_creates_vehicle_and_checks_in(self):
        response = self.client.post(reverse('entry_check_in'), {'manual_plate': 'up65ab1234'})
        data = response.json()
        self.assertEqual(data['plate'], 'UP65AB1234')
        self.assertEqual(data['slot_id'], 'A-101')
        self.assertTrue(Vehicle.objects.filter(plate='UP65AB1234').exists())

    def test_duplicate_entry_returns_conflict(self):
        self.client.post(reverse('entry_check_in'), {'manual_plate': 'UP65AB1234'})
        response = self.client.post(reverse('entry_check_in'), {'manual_plate': 'UP65AB1234'})
        self.assertEqual(response.status_code, 409)
        self.assertIn('error', response.json())

    def test_lot_full_returns_conflict(self):
        self.client.post(reverse('entry_check_in'), {'manual_plate': 'UP65AB1234'})
        response = self.client.post(reverse('entry_check_in'), {'manual_plate': 'DL01XY9999'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error'], 'Lot full.')

    def test_no_plate_and_no_images_returns_400(self):
        response = self.client.post(reverse('entry_check_in'), {})
        self.assertEqual(response.status_code, 400)
