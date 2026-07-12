import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from hr_app_backend.utils import AppError, get_env


RESEND_BASE_URL = 'https://api.resend.com'
RESEND_USER_AGENT = 'hr-app-backend/1.0 (+https://workiva.com.ng)'


class ResendError(AppError):
    status_code = 502

    def __init__(self, message=None, *, provider_status=None, provider_code=None, provider_message=None, response_body=None):
        super().__init__(message)
        self.provider_status = provider_status
        self.provider_code = provider_code
        self.provider_message = provider_message
        self.response_body = response_body


class ResendClient:
    def __init__(self, api_key=None, base_url=RESEND_BASE_URL, timeout=30):
        self.api_key = api_key or get_env('RESEND_API_KEY')
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

        if not self.api_key:
            raise ValueError('RESEND_API_KEY is required for email delivery.')

    def send_email(self, *, subject, body, from_email, to_emails, html_body=None, cc=None, bcc=None):
        payload = {
            'from': from_email,
            'to': to_emails,
            'subject': subject,
            'text': body,
        }
        if html_body:
            payload['html'] = html_body
        if cc:
            payload['cc'] = cc
        if bcc:
            payload['bcc'] = bcc
        return self.post('/emails', payload)

    def post(self, path, payload):
        body = json.dumps(payload).encode('utf-8')
        request = Request(
            url=f'{self.base_url}{path}',
            data=body,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': RESEND_USER_AGENT,
            },
            method='POST',
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            details = exc.read().decode('utf-8', errors='ignore')
            provider_code = None
            provider_message = None

            try:
                parsed = json.loads(details) if details else {}
            except json.JSONDecodeError:
                parsed = {}

            if isinstance(parsed, dict):
                provider_code = parsed.get('error', {}).get('code') if isinstance(parsed.get('error'), dict) else None
                provider_message = parsed.get('message')
                if not provider_message and isinstance(parsed.get('error'), dict):
                    provider_message = parsed.get('error', {}).get('message')

            if not provider_message:
                provider_message = details or exc.reason

            raise ResendError(
                f'Resend request failed with status {exc.code}: {provider_message}',
                provider_status=exc.code,
                provider_code=provider_code,
                provider_message=provider_message,
                response_body=details,
            ) from exc
        except URLError as exc:
            raise ResendError(
                f'Unable to reach Resend: {exc.reason}',
                provider_message=str(exc.reason),
            ) from exc


def get_resend_client():
    return ResendClient()
