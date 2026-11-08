from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from hr_app_backend.authentication.models import Organization, UserProfile
from hr_app_backend.utils.errors import ValidationError

from .models import Subscription
from .services.billing import public_provider_response, validate_callback_url, verify_subscription_payment

PAYSTACK = 'hr_app_backend.billing.services.billing.get_paystack_client'


def _paystack_response(*, status='success', amount=1500000, currency='NGN', reference='pst_ref'):
    return {
        'status': True,
        'message': 'Verification successful',
        'data': {
            'id': 99,
            'status': status,
            'reference': reference,
            'amount': amount,
            'currency': currency,
            'paid_at': '2026-11-08T10:00:00Z',
            'channel': 'card',
            'ip_address': '203.0.113.9',
            'customer': {'email': 'owner@example.com', 'phone': '+2348000000000'},
            'authorization': {'authorization_code': 'AUTH_secret', 'bin': '408408', 'last4': '4081'},
        },
    }


class SubscriptionVerifyTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Acme', email='owner@example.com', phone='1')
        self.user = get_user_model().objects.create_user(username='owner', email='owner@example.com', password='x')
        UserProfile.objects.create(
            user=self.user, account_type=UserProfile.ACCOUNT_TYPE_COMPANY, organization=self.organization,
        )
        self.subscription = Subscription.objects.create(
            organization=self.organization,
            created_by=self.user,
            plan=Subscription.PLAN_STARTER,
            provider=Subscription.PROVIDER_PAYSTACK,
            reference='pst_ref',
            amount=Decimal('15000.00'),
            currency='NGN',
            start_date=date(2026, 11, 8),
        )

    def _verify(self, response):
        client = MagicMock()
        client.verify_transaction.return_value = response
        with patch(PAYSTACK, return_value=client):
            result = verify_subscription_payment(self.user, {'reference': 'pst_ref'})
        return result, client

    def test_matching_payment_activates(self):
        (subscription, public, paid), _ = self._verify(_paystack_response())
        self.assertTrue(paid)
        self.assertEqual(subscription.status, Subscription.STATUS_ACTIVE)
        self.assertIsNotNone(subscription.paid_at)

    def test_underpayment_is_not_accepted(self):
        (subscription, _, paid), _ = self._verify(_paystack_response(amount=100))
        self.assertFalse(paid)
        self.assertEqual(subscription.status, Subscription.STATUS_FAILED)

    def test_wrong_currency_is_not_accepted(self):
        (subscription, _, paid), _ = self._verify(_paystack_response(currency='USD'))
        self.assertFalse(paid)
        self.assertNotEqual(subscription.status, Subscription.STATUS_ACTIVE)

    def test_abandoned_payment_stays_pending(self):
        (subscription, _, paid), _ = self._verify(_paystack_response(status='abandoned'))
        self.assertFalse(paid)
        self.assertEqual(subscription.status, Subscription.STATUS_PENDING)

    def test_reverify_of_active_subscription_never_downgrades(self):
        self._verify(_paystack_response())
        (subscription, _, paid), client = self._verify(_paystack_response(status='failed'))
        self.assertTrue(paid)
        self.assertEqual(subscription.status, Subscription.STATUS_ACTIVE)
        client.verify_transaction.assert_not_called()

    def test_response_hides_customer_and_card_details(self):
        (_, public, _), _ = self._verify(_paystack_response())
        flat = repr(public)
        for secret in ('AUTH_secret', '408408', '4081', '203.0.113.9', '+2348000000000'):
            self.assertNotIn(secret, flat)
        self.assertEqual(public['data']['status'], 'success')

    def test_public_provider_response_handles_empty(self):
        self.assertEqual(public_provider_response(None)['data']['status'], None)


class CallbackUrlTests(TestCase):
    @patch.dict('os.environ', {'PAYMENT_CALLBACK_ALLOWED_ORIGINS': 'https://app.workiva.com.ng'})
    def test_allowed_origin_passes(self):
        url = 'https://app.workiva.com.ng/billing/callback?x=1'
        self.assertEqual(validate_callback_url(url), url)

    @patch.dict('os.environ', {'PAYMENT_CALLBACK_ALLOWED_ORIGINS': 'https://app.workiva.com.ng'})
    def test_foreign_origin_is_rejected(self):
        for url in ('https://evil.example/phish', 'https://app.workiva.com.ng.evil.example/', 'javascript:alert(1)'):
            with self.assertRaises(ValidationError):
                validate_callback_url(url)

    @override_settings(DEBUG=False)
    @patch.dict('os.environ', {'PAYMENT_CALLBACK_ALLOWED_ORIGINS': '', 'FRONTEND_BILLING_URL': '', 'FRONTEND_LOGIN_URL': ''})
    def test_without_allow_list_production_requires_https(self):
        with self.assertRaises(ValidationError):
            validate_callback_url('http://anything.example/cb')
        self.assertTrue(validate_callback_url('https://anything.example/cb'))
