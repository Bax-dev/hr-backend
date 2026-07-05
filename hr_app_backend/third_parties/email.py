from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection


class EmailService:
    def __init__(self, connection=None, default_from_email=None):
        self.connection = connection or get_connection()
        self.default_from_email = default_from_email or settings.DEFAULT_FROM_EMAIL

    def send_mail(self, subject, body, to_emails, *, html_body=None, from_email=None, cc=None, bcc=None):
        message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email or self.default_from_email,
            to=to_emails,
            cc=cc or [],
            bcc=bcc or [],
            connection=self.connection,
        )

        if html_body:
            message.attach_alternative(html_body, "text/html")

        return message.send()


def get_email_service():
    return EmailService()
