from django.test import TestCase

from .models import ParkingSlot, Vehicle


class ParkingSlotTests(TestCase):
    def test_slot_id_is_primary_key(self):
        slot = ParkingSlot.objects.create(slot_id='A-101', zone_name='Ground Floor')
        self.assertEqual(ParkingSlot.objects.get(pk='A-101'), slot)

    def test_duplicate_slot_id_rejected(self):
        ParkingSlot.objects.create(slot_id='A-101', zone_name='Ground Floor')
        with self.assertRaises(Exception):
            ParkingSlot.objects.create(slot_id='A-101', zone_name='First Floor')


class VehicleTests(TestCase):
    def test_plate_is_uppercased_on_save(self):
        v = Vehicle.objects.create(plate='up65ab1234')
        self.assertEqual(v.plate, 'UP65AB1234')

    def test_vehicle_without_owner_is_valid(self):
        v = Vehicle.objects.create(plate='DL01XY9999')
        self.assertIsNone(v.owner)
