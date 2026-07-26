from django.utils import timezone

from hr_app_backend.services import render_email_template
from hr_app_backend.third_parties import get_email_service
from hr_app_backend.utils import get_env, timedelta, today_local

from ..models import Subscription

DEFAULT_BILLING_URL = 'http://localhost:5173/billing/start'

# (days remaining, field that records when that window's reminder was sent)
REMINDER_WINDOWS = (
    (5, 'reminder_5d_sent_at'),
    (2, 'reminder_2d_sent_at'),
    (1, 'reminder_1d_sent_at'),
)


def _plan_label(plan):
    return dict(Subscription.PLAN_CHOICES).get(plan, plan.replace('_', ' ').title())


def _billing_url():
    return get_env('FRONTEND_BILLING_URL', DEFAULT_BILLING_URL).strip() or DEFAULT_BILLING_URL


def _send_expiry_reminder(subscription, days_remaining):
    organization = subscription.organization
    recipient = subscription.created_by.email or organization.email
    if not recipient:
        return

    plan_label = _plan_label(subscription.plan)
    day_word = 'day' if days_remaining == 1 else 'days'
    end_date_display = subscription.end_date.strftime('%B %d, %Y')
    billing_url = _billing_url()

    get_email_service().send_mail(
        subject=f'Your {plan_label} plan expires in {days_remaining} {day_word}',
        body=(
            f'Your {plan_label} subscription for {organization.name} expires on {end_date_display} '
            f'({days_remaining} {day_word} from now). Renew at {billing_url} to avoid any interruption.'
        ),
        to_emails=[recipient],
        html_body=render_email_template(
            'emails/plan_expiry_reminder.html',
            {
                'email_title': 'Your subscription is expiring soon',
                'email_eyebrow': 'Billing',
                'email_heading': f'{plan_label} plan expires in {days_remaining} {day_word}',
                'email_intro': (
                    f'Renew before {end_date_display} to keep {organization.name} running without interruption.'
                ),
                'organization_name': organization.name,
                'plan_label': plan_label,
                'end_date': end_date_display,
                'days_remaining': days_remaining,
                'day_word': day_word,
                'billing_url': billing_url,
                'recipient_email': recipient,
            },
        ),
    )


def send_plan_expiry_reminders():
    """Email organizations whose active subscription expires in 5, 2, or 1 day(s).

    Meant to run once a day (e.g. via a cron-scheduled ``manage.py
    send_expiry_reminders``). Idempotent per subscription/window: each
    reminder field is stamped once it's sent, so re-running the same day, or
    catching up after a missed run, never double-sends.
    """
    today = today_local()
    sent_count = 0

    for days_remaining, field_name in REMINDER_WINDOWS:
        target_date = today + timedelta(days=days_remaining)
        subscriptions = Subscription.objects.filter(
            status=Subscription.STATUS_ACTIVE,
            end_date=target_date,
            **{field_name: None},
        ).select_related('organization', 'created_by')

        for subscription in subscriptions:
            _send_expiry_reminder(subscription, days_remaining)
            setattr(subscription, field_name, timezone.now())
            subscription.save(update_fields=[field_name, 'updated_at'])
            sent_count += 1

    return sent_count
