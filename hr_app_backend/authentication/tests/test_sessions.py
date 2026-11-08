import json
from datetime import timedelta

from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from hr_app_backend.authentication.models import LoginEvent, UserSession
from hr_app_backend.authentication.services import sessions
from hr_app_backend.middleware import RequestIDMiddleware
from hr_app_backend.third_parties import get_redis_client

from .base import FIREFOX_WIN, PASSWORD, AuthTestCase


class SessionTests(AuthTestCase):
    def test_login_creates_a_hashed_session_with_device_info(self):
        token = self.login_token()
        session = UserSession.objects.get(user=self.user)
        self.assertNotEqual(session.token_hash, token)
        self.assertEqual(session.token_hash, sessions.hash_token(token))
        self.assertEqual((session.device, session.browser), ('macOS', 'Chrome'))
        self.assertEqual(self.get('me/', token).status_code, 200)

    def test_logout_ends_the_token(self):
        token = self.login_token()
        self.assertEqual(self.post('logout/', token=token).status_code, 200)
        self.assertEqual(self.get('me/', token).status_code, 401)
        self.assertEqual(UserSession.objects.get(user=self.user).revoked_reason, UserSession.REVOKED_LOGOUT)

    def test_expired_session_is_rejected(self):
        token = self.login_token()
        UserSession.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.get('me/', token).status_code, 401)

    def test_disabled_account_is_signed_out_everywhere(self):
        token = self.login_token()
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertEqual(self.get('me/', token).status_code, 401)
        self.assertEqual(sessions.active_sessions(self.user).count(), 0)

    def test_list_sessions_marks_this_device(self):
        mine = self.login_token()
        self.login_token(ua=FIREFOX_WIN)
        response = self.get('sessions/', mine)
        rows = response.json()['data']['sessions']
        self.assertEqual(len(rows), 2)
        current = [row for row in rows if row['current']]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['browser'], 'Chrome')

    def test_revoke_one_session(self):
        mine = self.login_token()
        other = self.login_token(ua=FIREFOX_WIN)
        other_id = UserSession.objects.get(token_hash=sessions.hash_token(other)).pk
        self.assertEqual(self.delete(f'sessions/{other_id}/', mine).status_code, 200)
        self.assertEqual(self.get('me/', other).status_code, 401)
        self.assertEqual(self.get('me/', mine).status_code, 200)

    def test_cannot_revoke_someone_elses_session(self):
        intruder = self.make_user('eve@acme.test')
        mine = self.login_token()
        theirs = self.login_token(intruder.email)
        their_id = UserSession.objects.get(token_hash=sessions.hash_token(theirs)).pk
        self.assertEqual(self.delete(f'sessions/{their_id}/', mine).status_code, 404)
        self.assertEqual(self.get('me/', theirs).status_code, 200)

    def test_revoke_other_sessions_keeps_this_one(self):
        mine = self.login_token()
        others = [self.login_token(ua=FIREFOX_WIN), self.login_token()]
        response = self.post('sessions/revoke-others/', token=mine)
        self.assertEqual(response.json()['data']['sessions_revoked'], 2)
        self.assertEqual(self.get('me/', mine).status_code, 200)
        for token in others:
            self.assertEqual(self.get('me/', token).status_code, 401)

    def test_password_change_signs_out_other_devices_only(self):
        mine = self.login_token()
        other = self.login_token(ua=FIREFOX_WIN)
        response = self.post(
            'change-password/',
            {'current_password': PASSWORD, 'password': 'Brand-New-Secret-77', 'confirm_password': 'Brand-New-Secret-77'},
            token=mine,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['data']['sessions_revoked'], 1)
        self.assertEqual(self.get('me/', mine).status_code, 200)
        self.assertEqual(self.get('me/', other).status_code, 401)

    def test_password_change_rejects_reusing_the_current_password(self):
        mine = self.login_token()
        response = self.post(
            'change-password/',
            {'current_password': PASSWORD, 'password': PASSWORD, 'confirm_password': PASSWORD},
            token=mine,
        )
        self.assertEqual(response.status_code, 400)

    def test_legacy_redis_token_is_adopted_once(self):
        token = 'legacy-token-for-tests-0001'
        key = f'{sessions.LEGACY_SESSION_NAMESPACE}:{token}'
        client = get_redis_client()
        client.setex(key, 3600, json.dumps({'user_id': str(self.user.pk)}))
        self.addCleanup(client.delete, key)

        self.assertEqual(self.get('me/', token).status_code, 200)
        self.assertIsNone(client.get(key))
        session = UserSession.objects.get(token_hash=sessions.hash_token(token))
        self.assertLess(session.expires_at, timezone.now() + timedelta(hours=2))
        # Still valid afterwards, now from the database, and revocable like any other.
        self.assertEqual(self.get('me/', token).status_code, 200)
        self.post('logout/', token=token)
        self.assertEqual(self.get('me/', token).status_code, 401)


class LockoutTests(AuthTestCase):
    def test_five_wrong_passwords_lock_the_account(self):
        for _ in range(5):
            self.assertEqual(self.login(password='wrong').status_code, 401)
        response = self.login()  # even the right password is refused while locked
        self.assertEqual(response.status_code, 429)
        body = response.json()
        self.assertEqual(body['code'], 'TOO_MANY_ATTEMPTS')
        self.assertEqual(body['retry_after'], 900)
        self.assertFalse(UserSession.objects.filter(user=self.user).exists())

    def test_lockout_expires_after_the_window(self):
        for _ in range(5):
            self.login(password='wrong')
        LoginEvent.objects.update(created_at=timezone.now() - timedelta(minutes=16))
        self.assertEqual(self.login().status_code, 200)

    def test_successful_sign_in_resets_the_count(self):
        for _ in range(4):
            self.login(password='wrong')
        self.assertEqual(self.login().status_code, 200)
        for _ in range(4):
            self.login(password='wrong')
        self.assertEqual(self.login().status_code, 200)

    def test_unknown_email_is_locked_out_the_same_way(self):
        # Same shape as a real account: five 401s, then locked.
        statuses = [self.login('nobody@acme.test', password='x').status_code for _ in range(6)]
        self.assertEqual(statuses[:5], [401] * 5)
        self.assertEqual(statuses[5], 429)

    def test_wrong_password_and_unknown_email_look_the_same(self):
        known = self.login(password='wrong').json()
        unknown = self.login('nobody@acme.test', password='wrong').json()
        self.assertEqual(known['message'], unknown['message'])
        self.assertEqual(known['code'], unknown['code'])

    def test_login_history_records_failures_and_successes(self):
        self.login(password='wrong')
        token = self.login_token()
        events = self.get('login-history/', token).json()['data']['events']
        self.assertEqual([e['success'] for e in events], [True, False])
        self.assertEqual(events[1]['reason'], LoginEvent.REASON_WRONG_PASSWORD)
        self.assertEqual(events[0]['browser'], 'Chrome')


class RequestIdTests(SimpleTestCase):
    def _run(self, header):
        middleware = RequestIDMiddleware(lambda request: __import__('django.http').http.HttpResponse())
        request = RequestFactory().get('/', HTTP_X_REQUEST_ID=header)
        return middleware(request)['X-Request-ID']

    def test_uuid_is_kept(self):
        value = '3f2b8c9e-1d4a-4e6b-9f1a-2c3d4e5f6a7b'
        self.assertEqual(self._run(value), value)

    def test_anything_else_is_replaced(self):
        for bad in ['client-abc-12345', 'x' * 65, 'bad\nINFO forged line', 'semi;colon-1234']:
            self.assertNotEqual(self._run(bad), bad)
