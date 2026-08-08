import logging
from datetime import timedelta
from html import escape

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from hr_app_backend.employees.models import Employee
from hr_app_backend.third_parties.email import get_email_service

from .models import BulkNotification, Notification, NotificationEmailJob

logger = logging.getLogger(__name__)


@transaction.atomic
def enqueue_bulk_notification(*, organization, created_by, title, body, employee_ids=None):
    employees = Employee.objects.filter(organization=organization, status=Employee.STATUS_ACTIVE)
    if employee_ids is not None:
        employees = employees.filter(id__in=employee_ids)
    employees = list(employees.order_by('id'))

    campaign = BulkNotification.objects.create(
        organization=organization,
        created_by=created_by,
        title=title,
        body=body,
        recipient_count=len(employees),
        status=BulkNotification.STATUS_QUEUED if employees else BulkNotification.STATUS_COMPLETED,
    )
    Notification.objects.bulk_create([
        Notification(
            organization=organization,
            recipient=employee,
            title=title,
            body=body,
            category=Notification.CATEGORY_GENERAL,
        )
        for employee in employees
    ])
    NotificationEmailJob.objects.bulk_create([
        NotificationEmailJob(campaign=campaign, employee=employee, email=employee.email)
        for employee in employees
    ])
    return campaign


def _email_html(campaign, employee):
    name = escape(employee.first_name or 'there')
    body = escape(campaign.body).replace('\n', '<br>')
    return f'<p>Hello {name},</p><p>{body}</p>'


def _refresh_campaign(campaign_id):
    campaign = BulkNotification.objects.get(pk=campaign_id)
    jobs = campaign.email_jobs
    campaign.sent_count = jobs.filter(status=NotificationEmailJob.STATUS_SENT).count()
    campaign.failed_count = jobs.filter(status=NotificationEmailJob.STATUS_FAILED).count()
    unfinished = jobs.filter(status__in=[NotificationEmailJob.STATUS_PENDING, NotificationEmailJob.STATUS_PROCESSING]).exists()
    if unfinished:
        campaign.status = BulkNotification.STATUS_PROCESSING
    elif campaign.failed_count:
        campaign.status = BulkNotification.STATUS_COMPLETED_WITH_ERRORS
    else:
        campaign.status = BulkNotification.STATUS_COMPLETED
    campaign.save(update_fields=['sent_count', 'failed_count', 'status', 'updated_at'])


def process_email_queue(*, batch_size=100, max_attempts=3):
    """Claim and deliver one batch. Safe to run concurrently on PostgreSQL."""
    now = timezone.now()
    # A worker may be terminated after claiming a job. Make old claims eligible
    # again without disturbing jobs actively handled by another worker.
    NotificationEmailJob.objects.filter(
        status=NotificationEmailJob.STATUS_PROCESSING,
        updated_at__lte=now - timedelta(minutes=15),
    ).update(status=NotificationEmailJob.STATUS_PENDING, available_at=now)
    with transaction.atomic():
        jobs = list(
            NotificationEmailJob.objects.select_for_update(skip_locked=True)
            .select_related('campaign', 'employee')
            .filter(status=NotificationEmailJob.STATUS_PENDING, available_at__lte=now)
            .order_by('created_at')[:batch_size]
        )
        job_ids = [job.id for job in jobs]
        NotificationEmailJob.objects.filter(id__in=job_ids).update(status=NotificationEmailJob.STATUS_PROCESSING)

    affected_campaigns = set()
    email_service = get_email_service() if jobs else None
    for job in jobs:
        affected_campaigns.add(job.campaign_id)
        try:
            email_service.send_mail(
                job.campaign.title,
                job.campaign.body,
                [job.email],
                html_body=_email_html(job.campaign, job.employee),
            )
            NotificationEmailJob.objects.filter(pk=job.pk).update(
                status=NotificationEmailJob.STATUS_SENT,
                attempts=F('attempts') + 1,
                sent_at=timezone.now(),
                last_error='',
            )
        except Exception as exc:  # keep the worker alive and retry isolated recipients
            attempts = job.attempts + 1
            final = attempts >= max_attempts
            NotificationEmailJob.objects.filter(pk=job.pk).update(
                status=NotificationEmailJob.STATUS_FAILED if final else NotificationEmailJob.STATUS_PENDING,
                attempts=attempts,
                available_at=timezone.now() + timedelta(minutes=2 ** attempts),
                last_error=str(exc)[:2000],
            )
            logger.exception('Notification email job failed. job=%s attempt=%s', job.id, attempts)

    for campaign_id in affected_campaigns:
        _refresh_campaign(campaign_id)
    return len(jobs)
