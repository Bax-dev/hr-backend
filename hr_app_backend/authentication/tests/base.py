import json
import re
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from hr_app_backend.authentication.models import Organization, UserProfile
from hr_app_backend.authentication.services import mfa
from hr_app_backend.authentication.views.helpers import SESSION_COOKIE_NAME

User = get_user_model()

AUTH = '/api/v1/auth/'
PASSWORD = 'Correct-Horse-42'
CHROME_MAC = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/126.0 Safari/537.36'
)
FIREFOX_WIN = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0'

# Rate-limit counters live in the default cache; keep them in memory and per test so
# the many sign-ins below don't trip the per-IP throttles.
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=LOCMEM, SECURE_SSL_REDIRECT=False)
class AuthTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.organization = Organization.objects.create(name='Acme', email='hr@acme.test', phone='123')
        self.user = self.make_user('ada@acme.test')

    def make_user(self, email, password=PASSWORD, **extra):
        user = User.objects.create_user(username=email, email=email, password=password, **extra)
        UserProfile.objects.create(
            user=user,
            account_type=UserProfile.ACCOUNT_TYPE_COMPANY,
            full_name='Ada Lovelace',
            organization=self.organization,
            email_verified=True,
        )
        return user

    # ------------------------------------------------------------ http helpers

    # The session token is delivered as an httpOnly cookie. These tests juggle several
    # "devices", so each request sends exactly the token it is given (via the
    # Authorization fallback) and the client's cookie jar is emptied afterwards.

    def _send(self, method, path, token=None, **kwargs):
        if token:
            kwargs['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        self.client.cookies.clear()
        response = getattr(self.client, method)(AUTH + path, **kwargs)
        self.client.cookies.clear()
        return response

    def post(self, path, data=None, token=None, ua=CHROME_MAC, **headers):
        return self._send(
            'post', path, token, data=json.dumps(data or {}), content_type='application/json',
            HTTP_USER_AGENT=ua, **headers,
        )

    def get(self, path, token=None, **headers):
        return self._send('get', path, token, **headers)

    def delete(self, path, token=None):
        return self._send('delete', path, token)

    @staticmethod
    def token_of(response):
        """The session token a response set as a cookie, or None (e.g. an MFA challenge)."""
        cookie = response.cookies.get(SESSION_COOKIE_NAME)
        return cookie.value if cookie and cookie.value else None

    def login(self, email=None, password=PASSWORD, ua=CHROME_MAC):
        return self.post('login/', {'email': email or self.user.email, 'password': password}, ua=ua)

    def login_token(self, email=None, ua=CHROME_MAC):
        response = self.login(email, ua=ua)
        self.assertEqual(response.status_code, 200, response.content)
        token = self.token_of(response)
        self.assertTrue(token)
        self.assertNotIn('token', response.json()['data'])  # never exposed to JavaScript
        return token

    # ------------------------------------------------------------ email capture

    @contextmanager
    def capture_email(self, module):
        service = MagicMock()
        with patch(f'hr_app_backend.authentication.services.{module}.get_email_service', return_value=service):
            yield service

    @staticmethod
    def code_from(service):
        body = service.send_mail.call_args.kwargs['body']
        return re.search(r'\b(\d{6})\b', body).group(1)


class Clock:
    """Controls the time TOTP codes are generated and checked at."""

    def __init__(self, start=1_800_000_000):
        self.now = float(start)

    def advance(self, steps=1):
        self.now += mfa.PERIOD * steps

    def code(self, secret, offset=0):
        return mfa.hotp(secret, mfa.current_counter(self.now) + offset)

    def patch(self):
        return patch('hr_app_backend.authentication.services.mfa.time.time', side_effect=lambda: self.now)
