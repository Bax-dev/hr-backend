from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from hr_app_backend.authentication.models import LoginEvent, MfaChallenge, MfaDevice, MfaRecoveryCode, UserSession
from hr_app_backend.authentication.services import mfa
from hr_app_backend.authentication.services.password_reset import OTP_NAMESPACE
from hr_app_backend.authentication.services.otp import discard_code

from .base import FIREFOX_WIN, PASSWORD, AuthTestCase, Clock


class TotpPrimitiveTests(SimpleTestCase):
    def test_rfc4226_vectors(self):
        secret = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'  # base32 of "12345678901234567890"
        expected = ['755224', '287082', '359152', '969429', '338314']
        self.assertEqual([mfa.hotp(secret, i) for i in range(5)], expected)

    def test_drift_window(self):
        secret = mfa.generate_secret()
        now = 1_800_000_000
        counter = mfa.current_counter(now)
        self.assertEqual(mfa.matching_counter(secret, mfa.hotp(secret, counter - 1), at=now), counter - 1)
        self.assertEqual(mfa.matching_counter(secret, mfa.hotp(secret, counter + 1), at=now), counter + 1)
        self.assertIsNone(mfa.matching_counter(secret, mfa.hotp(secret, counter + 2), at=now))
        self.assertIsNone(mfa.matching_counter(secret, 'abcdef', at=now))

    def test_otpauth_url(self):
        url = mfa.otpauth_url('ABC', 'ada@acme.test')
        self.assertTrue(url.startswith('otpauth://totp/Workiva%3Aada%40acme.test?'))
        self.assertIn('issuer=Workiva', url)


class MfaTestCase(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.clock = Clock()
        patcher = self.clock.patch()
        patcher.start()
        self.addCleanup(patcher.stop)
        self.token = self.login_token()

    def enrol(self):
        setup = self.post('mfa/setup/', {'password': PASSWORD}, token=self.token).json()['data']
        secret = setup['secret']
        enabled = self.post('mfa/enable/', {'code': self.clock.code(secret)}, token=self.token)
        self.assertEqual(enabled.status_code, 200, enabled.content)
        self.clock.advance()
        return secret, enabled.json()['data']['recovery_codes']

    def challenge(self, ua=FIREFOX_WIN):
        response = self.login(ua=ua)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()['data']
        self.assertTrue(data['mfa_required'])
        return data['mfa_token']


class MfaEnrolmentTests(MfaTestCase):
    def test_setup_requires_the_password(self):
        response = self.post('mfa/setup/', {'password': 'wrong'}, token=self.token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'INVALID_PASSWORD')

    def test_setup_then_enable(self):
        status = self.get('mfa/', self.token).json()['data']
        self.assertFalse(status['enabled'])

        setup = self.post('mfa/setup/', {'password': PASSWORD}, token=self.token).json()['data']
        self.assertIn('otpauth://', setup['otpauth_url'])
        self.assertTrue(self.get('mfa/', self.token).json()['data']['pending_setup'])

        wrong = self.post('mfa/enable/', {'code': '000000'}, token=self.token)
        self.assertEqual(wrong.json()['code'], 'INVALID_MFA_CODE')

        data = self.post('mfa/enable/', {'code': self.clock.code(setup['secret'])}, token=self.token).json()['data']
        self.assertTrue(data['enabled'])
        self.assertEqual(len(data['recovery_codes']), 10)
        self.assertEqual(data['recovery_codes_remaining'], 10)

    def test_secret_and_recovery_codes_are_not_stored_in_plain_text(self):
        secret, codes = self.enrol()
        device = MfaDevice.objects.get(user=self.user)
        self.assertNotIn(secret, device.secret_encrypted)
        self.assertEqual(mfa.decrypt_secret(device.secret_encrypted), secret)
        stored = set(MfaRecoveryCode.objects.values_list('code_hash', flat=True))
        self.assertTrue(stored.isdisjoint(codes))

    def test_cannot_enrol_twice(self):
        self.enrol()
        response = self.post('mfa/setup/', {'password': PASSWORD}, token=self.token)
        self.assertEqual(response.status_code, 409)


class MfaSignInTests(MfaTestCase):
    def test_password_alone_no_longer_signs_in(self):
        self.enrol()
        response = self.login(ua=FIREFOX_WIN)
        data = response.json()['data']
        self.assertTrue(data['mfa_required'])
        self.assertIsNone(self.token_of(response))
        self.assertIsNone(self.token_of(response))
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 1)  # only setUp's

    def test_code_completes_sign_in(self):
        secret, _ = self.enrol()
        response = self.post('mfa/verify/', {'mfa_token': self.challenge(), 'code': self.clock.code(secret)})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()['data']
        self.assertEqual(data['method'], 'totp')
        self.assertEqual(self.get('me/', self.token_of(response)).status_code, 200)
        self.assertEqual(LoginEvent.objects.filter(user=self.user, success=True).count(), 2)

    def test_code_cannot_be_replayed(self):
        secret, _ = self.enrol()
        code = self.clock.code(secret)
        self.assertEqual(self.post('mfa/verify/', {'mfa_token': self.challenge(), 'code': code}).status_code, 200)
        replay = self.post('mfa/verify/', {'mfa_token': self.challenge(), 'code': code})
        self.assertEqual(replay.json()['code'], 'INVALID_MFA_CODE')

    def test_challenge_is_single_use(self):
        secret, _ = self.enrol()
        token = self.challenge()
        self.post('mfa/verify/', {'mfa_token': token, 'code': self.clock.code(secret)})
        self.clock.advance()
        again = self.post('mfa/verify/', {'mfa_token': token, 'code': self.clock.code(secret)})
        self.assertEqual(again.status_code, 401)
        self.assertEqual(again.json()['code'], 'MFA_CHALLENGE_INVALID')

    def test_expired_challenge(self):
        secret, _ = self.enrol()
        token = self.challenge()
        MfaChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.post('mfa/verify/', {'mfa_token': token, 'code': self.clock.code(secret)})
        self.assertEqual(response.status_code, 401)

    def test_five_wrong_codes_kill_the_challenge(self):
        secret, _ = self.enrol()
        token = self.challenge()
        statuses = [self.post('mfa/verify/', {'mfa_token': token, 'code': '000000'}).status_code for _ in range(5)]
        self.assertEqual(statuses, [400, 400, 400, 400, 429])
        response = self.post('mfa/verify/', {'mfa_token': token, 'code': self.clock.code(secret)})
        self.assertEqual(response.status_code, 401)

    def test_wrong_codes_count_towards_account_lockout(self):
        self.enrol()
        token = self.challenge()
        for _ in range(4):
            self.post('mfa/verify/', {'mfa_token': token, 'code': '000000'})
        self.login(password='wrong')
        self.assertEqual(self.login().status_code, 429)

    def test_recovery_code_works_once(self):
        _, codes = self.enrol()
        response = self.post('mfa/verify/', {'mfa_token': self.challenge(), 'recovery_code': codes[0].upper()})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['data']['method'], 'recovery_code')
        self.assertEqual(response.json()['data']['recovery_codes_remaining'], 9)
        again = self.post('mfa/verify/', {'mfa_token': self.challenge(), 'recovery_code': codes[0]})
        self.assertEqual(again.status_code, 400)

    def test_password_reset_does_not_bypass_mfa(self):
        self.enrol()
        with self.capture_email('password_reset') as service:
            self.post('forgot-password/', {'email': self.user.email})
        self.addCleanup(discard_code, OTP_NAMESPACE, self.user.email)
        response = self.post(
            'reset-password/',
            {
                'email': self.user.email,
                'otp': self.code_from(service),
                'password': 'Another-Strong-Pass-9',
                'confirm_password': 'Another-Strong-Pass-9',
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()['data']
        self.assertTrue(data['mfa_required'])
        self.assertIsNone(self.token_of(response))


class MfaManagementTests(MfaTestCase):
    def test_disable_needs_password_and_code(self):
        secret, _ = self.enrol()
        no_password = self.post('mfa/disable/', {'password': 'wrong', 'code': self.clock.code(secret)}, token=self.token)
        self.assertEqual(no_password.status_code, 400)
        wrong_code = self.post('mfa/disable/', {'password': PASSWORD, 'code': '000000'}, token=self.token)
        self.assertEqual(wrong_code.status_code, 400)
        self.assertTrue(mfa.enabled_for(self.user))

        ok = self.post('mfa/disable/', {'password': PASSWORD, 'code': self.clock.code(secret)}, token=self.token)
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertFalse(ok.json()['data']['enabled'])
        self.assertFalse(MfaRecoveryCode.objects.filter(user=self.user).exists())
        self.assertTrue(self.token_of(self.login()))

    def test_disable_signs_out_other_devices(self):
        secret, _ = self.enrol()
        other = self.post('mfa/verify/', {'mfa_token': self.challenge(), 'code': self.clock.code(secret)})
        other_token = self.token_of(other)
        self.clock.advance()
        self.post('mfa/disable/', {'password': PASSWORD, 'code': self.clock.code(secret)}, token=self.token)
        self.assertEqual(self.get('me/', other_token).status_code, 401)
        self.assertEqual(self.get('me/', self.token).status_code, 200)

    def test_disable_with_a_recovery_code(self):
        _, codes = self.enrol()
        ok = self.post('mfa/disable/', {'password': PASSWORD, 'recovery_code': codes[3]}, token=self.token)
        self.assertEqual(ok.status_code, 200, ok.content)

    def test_regenerate_recovery_codes_replaces_the_old_ones(self):
        secret, old = self.enrol()
        response = self.post('mfa/recovery-codes/', {'password': PASSWORD, 'code': self.clock.code(secret)}, token=self.token)
        self.assertEqual(response.status_code, 200, response.content)
        new = response.json()['data']['recovery_codes']
        self.assertTrue(set(old).isdisjoint(new))
        stale = self.post('mfa/verify/', {'mfa_token': self.challenge(), 'recovery_code': old[0]})
        self.assertEqual(stale.status_code, 400)

    def test_management_endpoints_require_sign_in(self):
        for path in ['mfa/setup/', 'mfa/enable/', 'mfa/disable/', 'mfa/recovery-codes/']:
            self.assertEqual(self.post(path, {}).status_code, 401, path)
        self.assertEqual(self.get('mfa/').status_code, 401)
