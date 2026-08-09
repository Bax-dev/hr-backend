import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from hr_app_backend.utils import AppError, get_env

logger = logging.getLogger(__name__)

PAYSTACK_BASE_URL = "https://api.paystack.co"
PAYSTACK_USER_AGENT = "hr-app-backend/1.0 (+https://workiva.com.ng)"


class PaystackError(AppError):
    status_code = 502


class PaystackClient:
    def __init__(self, secret_key=None, base_url=PAYSTACK_BASE_URL, timeout=30):
        self.secret_key = secret_key or get_env("PAYSTACK_SECRET_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        if not self.secret_key:
            raise ValueError("PAYSTACK_SECRET_KEY is required for Paystack requests.")

    def initialize_transaction(self, *, email, amount, reference=None, callback_url=None, metadata=None, currency="NGN"):
        payload = {
            "email": email,
            "amount": amount,
            "currency": currency,
        }
        if reference:
            payload["reference"] = reference
        if callback_url:
            payload["callback_url"] = callback_url
        if metadata is not None:
            payload["metadata"] = metadata

        return self.post("/transaction/initialize", payload)

    def verify_transaction(self, reference):
        return self.get(f"/transaction/verify/{reference}")

    def list_banks(self, *, country="nigeria", use_cursor_pagination=True, per_page=None, pay_with_bank=False):
        params = {
            "country": country,
            "use_cursor": str(use_cursor_pagination).lower(),
            "pay_with_bank": str(pay_with_bank).lower(),
        }
        if per_page is not None:
            params["perPage"] = per_page

        return self.get("/bank", params=params)

    def get(self, path, params=None):
        query = f"?{urlencode(params)}" if params else ""
        return self._request("GET", f"{path}{query}")

    def post(self, path, payload):
        return self._request("POST", path, payload)

    def _request(self, method, path, payload=None):
        body = None
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": PAYSTACK_USER_AGENT,
        }

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        request = Request(
            url=f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            logger.warning("Paystack request to %s failed with status %s: %s", path, exc.code, details)
            raise PaystackError("The payment provider could not process this request. Please try again.") from exc
        except URLError as exc:
            logger.warning("Unable to reach Paystack for %s: %s", path, exc.reason)
            raise PaystackError("The payment provider is currently unreachable. Please try again.") from exc


def get_paystack_client():
    return PaystackClient()
