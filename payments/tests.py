from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import ParkingSlot, Vehicle
from parking.models import Tariff, Transaction
from parking.services import allocate_and_check_in, check_out
from .models import Payment
from .services import create_order, verify_and_close, PaymentError

CustomUser = get_user_model()


@override_settings(RAZORPAY_KEY_ID='rzp_test_fake', RAZORPAY_KEY_SECRET='fake_secret')
class CreateOrderTests(TestCase):
    def setUp(self):
        ParkingSlot.objects.create(slot_id='A-101', zone_name='Ground Floor')
        Tariff.objects.create(hourly_rate=20, min_charge=20, is_active=True)
        self.vehicle = Vehicle.objects.create(plate='UP65AB1234')
        allocate_and_check_in(self.vehicle)
        self.txn = check_out(self.vehicle)

    @patch('payments.services.razorpay.Client')
    def test_create_order_stores_correct_amount(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.order.create.return_value = {'id': 'order_fake123'}
        mock_client_cls.return_value = mock_client

        payment, order = create_order(self.txn)

        self.assertEqual(payment.amount_paise, int(self.txn.fee * 100))
        self.assertEqual(payment.razorpay_order_id, 'order_fake123')
        self.assertEqual(payment.status, Payment.Status.CREATED)

    def test_create_order_rejects_non_awaiting_transaction(self):
        self.txn.status = Transaction.Status.CLOSED
        self.txn.save()
        with self.assertRaises(PaymentError):
            create_order(self.txn)


@override_settings(RAZORPAY_KEY_ID='rzp_test_fake', RAZORPAY_KEY_SECRET='fake_secret')
class VerifyAndCloseTests(TestCase):
    def setUp(self):
        ParkingSlot.objects.create(slot_id='A-101', zone_name='Ground Floor')
        Tariff.objects.create(hourly_rate=20, min_charge=20, is_active=True)
        self.vehicle = Vehicle.objects.create(plate='UP65AB1234')
        allocate_and_check_in(self.vehicle)
        self.txn = check_out(self.vehicle)

        with patch('payments.services.razorpay.Client') as mock_client_cls:
            mock_client = MagicMock()
            mock_client.order.create.return_value = {'id': 'order_fake123'}
            mock_client_cls.return_value = mock_client
            self.payment, _ = create_order(self.txn)

    @patch('payments.services.razorpay.Client')
    def test_valid_signature_closes_transaction(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_client_cls.return_value = mock_client

        verify_and_close(self.txn, 'order_fake123', 'pay_fake456', 'sig_fake789')

        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, Transaction.Status.CLOSED)

        slot = ParkingSlot.objects.get(pk='A-101')
        self.assertFalse(slot.is_currently_occupied)

    @patch('payments.services.razorpay.Client')
    def test_invalid_signature_rejected(self, mock_client_cls):
        import razorpay
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.side_effect = razorpay.errors.SignatureVerificationError('bad sig')
        mock_client_cls.return_value = mock_client

        with self.assertRaises(PaymentError):
            verify_and_close(self.txn, 'order_fake123', 'pay_fake456', 'wrong_sig')

        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, Transaction.Status.AWAITING_PAYMENT)

        slot = ParkingSlot.objects.get(pk='A-101')
        self.assertTrue(slot.is_currently_occupied)

    def test_order_id_mismatch_rejected(self):
        with self.assertRaises(PaymentError):
            verify_and_close(self.txn, 'wrong_order_id', 'pay_fake456', 'sig_fake789')

    @patch('payments.services.razorpay.Client')
    def test_double_close_is_safe_noop(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.utility.verify_payment_signature.return_value = True
        mock_client_cls.return_value = mock_client

        verify_and_close(self.txn, 'order_fake123', 'pay_fake456', 'sig_fake789')
        # second call should not raise or double-free
        verify_and_close(self.txn, 'order_fake123', 'pay_fake456', 'sig_fake789')

        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, Transaction.Status.CLOSED)
