from hr_app_backend.authentication.services import otp
from hr_app_backend.authentication.services.password_reset import OTP_NAMESPACE, reset_password
from hr_app_backend.authentication.services.signup_otp import SIGNUP_OTP_NAMESPACE
from hr_app_backend.third_parties import get_redis_client
from hr_app_backend.utils.errors import ValidationError

from .base import FIREFOX_WIN, PASSWORD, AuthTestCase

NEW_PASSWORD = 'Another-Strong-Pass-9'


class PasswordResetTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(otp.discard_code, OTP_NAMESPACE, self.user.email)

    def request_code(self, email=None):
        with self.capture_email('password_reset') as service:
            response = self.post('forgot-password/', {'email': email or self.user.email})
        return response, service

    def reset(self, code, password=NEW_PASSWORD):
        return self.post(
            'reset-password/',
            {'email': self.user.email, 'otp': code, 'password': password, 'confirm_password': password},
        )

    def test_unknown_email_gets_the_same_response_and_no_mail(self):
        known, known_mail = self.request_code()
        unknown, unknown_mail = self.request_code('nobody@acme.test')
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(set(known.json()['data']), set(unknown.json()['data']))
        known_mail.send_mail.assert_called_once()
        unknown_mail.send_mail.assert_not_called()

    def test_code_is_stored_hashed(self):
        _, service = self.request_code()
        code = self.code_from(service)
        code_key, _ = otp._keys(OTP_NAMESPACE, self.user.email)
        stored = get_redis_client().get(code_key)
        self.assertTrue(stored)
        self.assertNotIn(code, stored)

    def test_reset_signs_out_every_existing_session(self):
        old = self.login_token()
        _, service = self.request_code()
        response = self.reset(self.code_from(service))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.get('me/', old).status_code, 401)
        self.assertEqual(self.get('me/', self.token_of(response)).status_code, 200)

    def test_code_is_burned_after_five_wrong_guesses(self):
        _, service = self.request_code()
        code = self.code_from(service)
        wrong = '000000' if code != '000000' else '111111'
        bodies = [self.reset(wrong).json() for _ in range(5)]
        self.assertEqual(bodies[-1]['code'], 'OTP_ATTEMPTS_EXCEEDED')
        # The endpoint's own 5/min limit is now hit too, so check the code directly.
        with self.assertRaises(ValidationError):
            otp.check_code(OTP_NAMESPACE, self.user.email, code)
        self.assertEqual(self.login(password=PASSWORD, ua=FIREFOX_WIN).status_code, 200)

    def test_weak_new_password_does_not_burn_an_attempt(self):
        _, service = self.request_code()
        code = self.code_from(service)
        for _ in range(otp.MAX_ATTEMPTS):
            with self.assertRaises(ValidationError):
                reset_password(self.user.email, code, 'short', 'short')
        self.assertEqual(self.reset(code).status_code, 200)

    def test_code_works_only_once(self):
        _, service = self.request_code()
        code = self.code_from(service)
        self.assertEqual(self.reset(code).status_code, 200)
        self.assertEqual(self.reset(code, password='Yet-Another-Pass-31').status_code, 400)


class SignupOtpTests(AuthTestCase):
    def test_resend_for_unknown_email_looks_successful(self):
        with self.capture_email('signup_otp') as service:
            response = self.post('resend-signup-otp/', {'email': 'nobody@acme.test'})
        self.assertEqual(response.status_code, 200)
        service.send_mail.assert_not_called()

    def test_verify_signup_code(self):
        self.addCleanup(otp.discard_code, SIGNUP_OTP_NAMESPACE, self.user.email)
        self.user.profile.email_verified = False
        self.user.profile.save(update_fields=['email_verified'])
        with self.capture_email('signup_otp') as service:
            self.post('resend-signup-otp/', {'email': self.user.email})
        response = self.post('verify-signup-otp/', {'email': self.user.email, 'otp': self.code_from(service)})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(self.token_of(response))
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.email_verified)
