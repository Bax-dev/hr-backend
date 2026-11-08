"""Local-development email "delivery": print messages to the server log instead of sending them.

Enabled with EMAIL_DELIVERY=console, and only allowed when DJANGO_DEBUG is on (settings.py
refuses to start otherwise), because the output contains one-time codes and invite links.

It logs through the ``hr_app_backend.dev_email`` logger, which has its own handler without
the secret-redaction filter. Otherwise "password: 123456" and "?token=..." would be masked,
which is exactly what you need to read when testing.
"""

import logging
import re
import uuid

logger = logging.getLogger('hr_app_backend.dev_email')

_CODE = re.compile(r'\b(\d{6})\b')
_URL = re.compile(r'https?://\S+')


class ConsoleEmailClient:
    def send_email(self, *, subject, body, from_email, to_emails, html_body=None, cc=None, bcc=None):
        text = body or ''
        lines = [
            '',
            '=' * 72,
            f'DEV EMAIL (not sent)  to={", ".join(to_emails)}  from={from_email}',
            f'Subject: {subject}',
        ]
        codes = sorted(set(_CODE.findall(text)))
        if codes:
            lines.append(f'>>> Code: {", ".join(codes)}')
        for url in _URL.findall(text):
            lines.append(f'>>> Link: {url.rstrip(".,)")}')
        lines += ['-' * 72, text.strip(), '=' * 72]
        logger.warning('\n'.join(lines))
        return {'id': f'console-{uuid.uuid4()}'}
