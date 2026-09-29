from django.test import TestCase, Client
from django.test.utils import override_settings

from .models import ANPRLog
from .pipeline import PLATE_REGEX, fix_ambiguous_chars, vote_across_frames, ReadResult


class PlateRegexTests(TestCase):
    def test_valid_10_char_plate(self):
        self.assertTrue(PLATE_REGEX.match('UP65AB1234'))

    def test_valid_9_char_plate(self):
        self.assertTrue(PLATE_REGEX.match('DL01C1234'))

    def test_invalid_plate_rejected(self):
        self.assertFalse(PLATE_REGEX.match('12ABCD34'))
        self.assertFalse(PLATE_REGEX.match(''))
        self.assertFalse(PLATE_REGEX.match('UP65AB12'))


class AmbiguousCharFixTests(TestCase):
    def test_o_to_zero_in_digit_position(self):
        self.assertEqual(fix_ambiguous_chars('DLO1XY9999'), 'DL01XY9999')

    def test_zero_to_o_in_letter_position(self):
        # pattern LLDDLLDDDD: position 4 (0-indexed) expects a letter; a stray 0 there
        # should be corrected to O
        self.assertEqual(fix_ambiguous_chars('UP650B1234'), 'UP65OB1234')

    def test_unknown_length_returned_unchanged(self):
        self.assertEqual(fix_ambiguous_chars('SHORT'), 'SHORT')


class VotingTests(TestCase):
    def test_majority_vote_wins(self):
        results = [
            ReadResult('UP65AB1234', 90, 'UP65AB1234', True),
            ReadResult('UP65AB1234', 85, 'UP65AB1234', True),
            ReadResult('DL01XY9999', 70, 'DL01XY9999', True),
        ]
        plate, conf, _ = vote_across_frames(results)
        self.assertEqual(plate, 'UP65AB1234')
        self.assertEqual(conf, 90)

    def test_no_valid_reads_returns_none(self):
        results = [
            ReadResult(None, 20, 'garbage', False),
            ReadResult(None, 15, 'noise', False),
        ]
        plate, conf, raw = vote_across_frames(results)
        self.assertIsNone(plate)
        self.assertEqual(conf, 20)


class DeviceEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()

    @override_settings(DEVICE_API_KEY='test-device-key-123')
    def test_missing_key_rejected(self):
        response = self.client.post('/api/anpr/entry/', {})
        self.assertEqual(response.status_code, 401)

    @override_settings(DEVICE_API_KEY='test-device-key-123')
    def test_wrong_key_rejected(self):
        response = self.client.post('/api/anpr/entry/', {}, headers={'x-device-key': 'wrong'})
        self.assertEqual(response.status_code, 401)

    @override_settings(DEVICE_API_KEY='test-device-key-123')
    def test_correct_key_no_images_returns_400(self):
        response = self.client.post('/api/anpr/entry/', {}, headers={'x-device-key': 'test-device-key-123'})
        self.assertEqual(response.status_code, 400)

    @override_settings(DEVICE_API_KEY='test-device-key-123')
    def test_invalid_gate_rejected(self):
        response = self.client.post('/api/anpr/sideways/', {}, headers={'x-device-key': 'test-device-key-123'})
        self.assertEqual(response.status_code, 400)

    @override_settings(DEVICE_API_KEY='test-device-key-123')
    def test_correct_key_with_real_image_reads_plate(self):
        with open('anpr_scratch/plate_clean.png', 'rb') as f:
            response = self.client.post(
                '/api/anpr/entry/',
                {'images': f},
                headers={'x-device-key': 'test-device-key-123'},
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['plate'], 'UP65AB1234')
        self.assertEqual(ANPRLog.objects.count(), 1)
        self.assertTrue(ANPRLog.objects.first().success)
