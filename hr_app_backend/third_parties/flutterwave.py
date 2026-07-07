import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from hr_app_backend.utils import AppError, get_env


FLUTTERWAVE_BASE_URL = 'https://api.flutterwave.com/v3'


class FlutterwaveError(AppError):
    status_code = 502


class FlutterwaveClient:
    def __init__(self, secret_key=None, base_url=FLUTTERWAVE_BASE_URL, timeout=30):
        self.secret_key = secret_key or get_env('FLUTTERWAVE_SECRET_KEY')
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

        if not self.secret_key:
            raise ValueError('FLUTTERWAVE_SECRET_KEY is required for Flutterwave requests.')

    def initialize_payment(self, *, tx_ref, amount, currency, redirect_url, customer, customizations=None, meta=None):
        payload = {
            'tx_ref': tx_ref,
            'amount': amount,
            'currency': currency,
            'redirect_url': redirect_url,
            'customer': customer,
        }
        if customizations is not None:
            payload['customizations'] = customizations
        if meta is not None:
            payload['meta'] = meta
        return self.post('/payments', payload)

    def verify_transaction(self, reference):
        return self.get('/transactions/verify_by_reference', params={'tx_ref': reference})

    def get(self, path, params=None):
        query = f'?{urlencode(params)}' if params else ''
        return self._request('GET', f'{path}{query}')

    def post(self, path, payload):
        return self._request('POST', path, payload)

    def _request(self, method, path, payload=None):
        body = None
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }

        if payload is not None:
            body = json.dumps(payload).encode('utf-8')

        request = Request(
            url=f'{self.base_url}{path}',
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            details = exc.read().decode('utf-8', errors='ignore')
            raise FlutterwaveError(f'Flutterwave request failed with status {exc.code}: {details}') from exc
        except URLError as exc:
            raise FlutterwaveError(f'Unable to reach Flutterwave: {exc.reason}') from exc



def get_flutterwave_client():
    return FlutterwaveClient()
