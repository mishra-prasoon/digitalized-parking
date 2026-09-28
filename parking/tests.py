import threading

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from core.models import ParkingSlot, Vehicle
from booking.models import Booking
from parking.models import Tariff, Transaction
from parking.services import allocate_and_check_in, check_out, calculate_fee, AllocationError

CustomUser = get_user_model()


class AllocationTests(TestCase):
    def setUp(self):
        self.slot1 = ParkingSlot.objects.create(slot_id='A-101', zone_name='Ground Floor')
        self.slot2 = ParkingSlot.objects.create(slot_id='A-102', zone_name='Ground Floor')
        self.vehicle = Vehicle.objects.create(plate='UP65AB1234')
        Tariff.objects.create(hourly_rate=20, min_charge=20, is_active=True)

    def test_allocate_assigns_free_slot(self):
        txn = allocate_and_check_in(self.vehicle)
        self.assertEqual(txn.status, Transaction.Status.OPEN)
        self.assertIn(txn.slot_id, ['A-101', 'A-102'])

    def test_duplicate_entry_rejected(self):
        allocate_and_check_in(self.vehicle)
        with self.assertRaises(AllocationError):
            allocate_and_check_in(self.vehicle)

    def test_lot_full(self):
        v2 = Vehicle.objects.create(plate='DL01XY9999')
        v3 = Vehicle.objects.create(plate='MH12ZZ0001')
        allocate_and_check_in(self.vehicle)
        allocate_and_check_in(v2)
        with self.assertRaises(AllocationError):
            allocate_and_check_in(v3)

    def test_prebooked_vehicle_gets_reserved_slot(self):
        user = CustomUser.objects.create_user(username='u1', password='pass12345')
        owned_vehicle = Vehicle.objects.create(plate='RJ14AB5678', owner=user)
        now = timezone.now()
        Booking.objects.create(
            user=user, vehicle=owned_vehicle, slot=self.slot2,
            start_time=now - timezone.timedelta(minutes=5),
            end_time=now + timezone.timedelta(hours=1),
        )
        txn = allocate_and_check_in(owned_vehicle)
        self.assertEqual(txn.slot_id, 'A-102')

    def test_walkin_blocked_from_slot_with_imminent_booking(self):
        user = CustomUser.objects.create_user(username='u2', password='pass12345')
        owned_vehicle = Vehicle.objects.create(plate='HR26CD1111', owner=user)
        now = timezone.now()
        Booking.objects.create(
            user=user, vehicle=owned_vehicle, slot=self.slot1,
            start_time=now + timezone.timedelta(minutes=30),
            end_time=now + timezone.timedelta(hours=1, minutes=30),
        )
        walkin = Vehicle.objects.create(plate='PB03EF2222')
        txn = allocate_and_check_in(walkin)
        self.assertEqual(txn.slot_id, 'A-102')  # A-101 excluded due to buffer


class FeeCalculationTests(TestCase):
    def setUp(self):
        self.tariff = Tariff.objects.create(hourly_rate=20, min_charge=20, is_active=True)

    def test_minimum_charge_applied(self):
        entry = timezone.now()
        exit_ = entry + timezone.timedelta(minutes=10)
        self.assertEqual(calculate_fee(entry, exit_, self.tariff), 20)

    def test_rounds_up_partial_hour(self):
        entry = timezone.now()
        exit_ = entry + timezone.timedelta(hours=1, minutes=15)
        self.assertEqual(calculate_fee(entry, exit_, self.tariff), 40)

    def test_exact_hours(self):
        entry = timezone.now()
        exit_ = entry + timezone.timedelta(hours=3)
        self.assertEqual(calculate_fee(entry, exit_, self.tariff), 60)


class CheckOutTests(TestCase):
    def setUp(self):
        ParkingSlot.objects.create(slot_id='A-101', zone_name='Ground Floor')
        self.vehicle = Vehicle.objects.create(plate='UP65AB1234')
        Tariff.objects.create(hourly_rate=20, min_charge=20, is_active=True)

    def test_checkout_no_open_session_rejected(self):
        with self.assertRaises(AllocationError):
            check_out(self.vehicle)

    def test_checkout_sets_awaiting_payment(self):
        allocate_and_check_in(self.vehicle)
        txn = check_out(self.vehicle)
        self.assertEqual(txn.status, Transaction.Status.AWAITING_PAYMENT)
        self.assertGreaterEqual(txn.fee, 20)


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.num_slots = 10
        for i in range(1, self.num_slots + 1):
            ParkingSlot.objects.create(slot_id=f'C-{i:03d}', zone_name='Test Zone')
        Tariff.objects.create(hourly_rate=20, min_charge=20, is_active=True)
        self.vehicles = [
            Vehicle.objects.create(plate=f'TEST{i:04d}XX') for i in range(20)
        ]

    def test_no_slot_double_assigned_under_concurrency(self):
        results = []
        lock = threading.Lock()

        def worker(vehicle):
            try:
                txn = allocate_and_check_in(vehicle)
                with lock:
                    results.append(('ok', txn.slot_id))
            except AllocationError:
                with lock:
                    results.append(('full', None))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker, args=(v,)) for v in self.vehicles]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r[0] == 'ok']
        failures = [r for r in results if r[0] == 'full']
        assigned_slots = [r[1] for r in successes]

        self.assertEqual(len(successes), self.num_slots)
        self.assertEqual(len(failures), len(self.vehicles) - self.num_slots)
        self.assertEqual(len(assigned_slots), len(set(assigned_slots)))  # no duplicates
