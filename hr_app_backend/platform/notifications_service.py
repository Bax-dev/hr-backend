"""Helpers for creating per-recipient inbox notifications.

Kept in its own module (importing only :mod:`platform.models`) so that other
apps — e.g. ``leave`` and the payroll views — can emit notifications without
creating an import cycle with ``platform.views``.
"""

from .models import Notification


def create_notification(*, recipient, title, body='', category=Notification.CATEGORY_GENERAL, organization=None):
    """Create an inbox notification for ``recipient`` (an ``Employee``).

    ``organization`` defaults to the recipient's organization. Returns ``None``
    when there is no recipient, so callers can fire-and-forget for accounts that
    have no linked employee record.
    """
    if recipient is None:
        return None

    return Notification.objects.create(
        organization=organization or recipient.organization,
        recipient=recipient,
        title=title,
        body=body,
        category=category,
    )
