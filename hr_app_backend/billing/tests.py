import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from hr_app_backend.billing.services import signup_checkout
from hr_app_backend.third_parties import get_redis_client

User = get_user_model()
PASSWORD = 'Paid-Signup-Pass-55'


class PaidSignupCheckoutTests(TestCase):
    def setUp(self):
        self.paystack = MagicMock()
        self.paystack.initialize_transaction.return_value = {'data': {'authorization_url': 'https://pay.test/x'}}
        patcher = patch.object(signup_checkout, 'get_paystack_client', return_value=self.paystack)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Pin the callback allow-list so the result doesn't depend on the local .env.
        origins = patch(
            'hr_app_backend.billing.services.billing.allowed_callback_origins', return_value={'https://app.test'}
        )
        origins.start()
        self.addCleanup(origins.stop)
        # Signup sends a verification email; keep it off the network.
        mail = patch('hr_app_backend.authentication.services.signup_otp.get_email_service', return_value=MagicMock())
        mail.start()
        self.addCleanup(mail.stop)

    def _initialize(self):
        result = signup_checkout.initialize_paid_signup_checkout({
            'account_type': 'company',
            'company_name': 'Paid Co',
            'email': 'owner@paid.test',
            'phone': '0800',
            'password': PASSWORD,
            'confirm_password': PASSWORD,
            'plan': 'starter',
            'billing_cycle': 'monthly',
            'callback_url': 'https://app.test/billing/callback',
        })
        key = signup_checkout._pending_key(result['reference'])
        self.addCleanup(get_redis_client().delete, key)
        return result['reference'], key

    def test_pending_signup_never_holds_the_raw_password(self):
        _, key = self._initialize()
        raw = get_redis_client().get(key)
        self.assertNotIn(PASSWORD, raw)
        signup = json.loads(raw)['signup']
        self.assertNotIn('password', signup)
        self.assertNotIn('confirm_password', signup)
        self.assertTrue(signup['password_hash'])

    def test_verified_payment_creates_an_account_with_the_chosen_password(self):
        reference, _ = self._initialize()
        self.paystack.verify_transaction.return_value = {
            'status': True,
            'data': {'status': 'success', 'amount': 1500000, 'currency': 'NGN', 'id': 1},
        }
        _, session, _ = signup_checkout.verify_paid_signup_checkout(reference)
        self.assertIn('token', session)
        user = User.objects.get(email='owner@paid.test')
        self.assertTrue(user.check_password(PASSWORD))
