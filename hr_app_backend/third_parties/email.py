import logging

from django.conf import settings

from hr_app_backend.utils.errors import ExternalServiceError
from .resend import ResendError, get_resend_client

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, client=None, default_from_email=None):
        self.client = client or get_resend_client()
        self.default_from_email = default_from_email or self._resolve_default_from_email()

    def _resolve_default_from_email(self):
        default_from_email = (settings.DEFAULT_FROM_EMAIL or '').strip()
        if not default_from_email:
            default_from_email = (settings.EMAIL_HOST_USER or '').strip()
        if not default_from_email:
            raise ExternalServiceError('A default from email address must be configured for email delivery.')
        return default_from_email

    def send_mail(self, subject, body, to_emails, *, html_body=None, from_email=None, cc=None, bcc=None):
        sender = from_email or self.default_from_email
        try:
            return self.client.send_email(
                subject=subject,
                body=body,
                from_email=sender,
                to_emails=to_emails,
                html_body=html_body,
                cc=cc or [],
                bcc=bcc or [],
            )
        except ResendError as exc:
            logger.exception(
                'Email delivery failed via Resend. from=%s to=%s status=%s provider_code=%s provider_message=%s response_body=%s',
                sender,
                ','.join(to_emails),
                exc.provider_status,
                exc.provider_code,
                exc.provider_message,
                exc.response_body,
            )
            message = 'Unable to send email at the moment. Please try again later.'
            if settings.DEBUG:
                details = []
                if exc.provider_status:
                    details.append(f'status={exc.provider_status}')
                if exc.provider_code:
                    details.append(f'code={exc.provider_code}')
                if exc.provider_message:
                    details.append(f'message={exc.provider_message}')
                if not details:
                    details.append(str(exc))
                message = f"{message} Provider response: {'; '.join(details)}"
            raise ExternalServiceError(message) from exc


def get_email_service():
    return EmailService()
