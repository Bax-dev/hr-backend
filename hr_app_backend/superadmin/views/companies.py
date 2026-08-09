import logging

from django.db.models import Prefetch
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from hr_app_backend.audit_logs.services import record_audit_event_safely
from hr_app_backend.authentication.models import Organization, UserProfile
from hr_app_backend.authentication.views.helpers import error_response, load_json
from hr_app_backend.billing.models import Subscription
from hr_app_backend.services import render_email_template
from hr_app_backend.third_parties import get_email_service
from hr_app_backend.utils.errors import AppError, NotFoundError, ValidationError
from hr_app_backend.utils.pagination import paginate_queryset

from .helpers import require_superuser

logger = logging.getLogger(__name__)


def _latest_subscription(org):
    subs = getattr(org, '_subs', None)
    return subs[0] if subs else None


def _bucket_for(org):
    if org.status == Organization.STATUS_SUSPENDED:
        return 'suspended'
    sub = _latest_subscription(org)
    if sub is None:
        return 'trial'
    if sub.plan == Subscription.PLAN_FREE_TRIAL and sub.status == Subscription.STATUS_ACTIVE:
        return 'trial'
    if sub.status == Subscription.STATUS_ACTIVE:
        return 'active'
    if sub.status in (Subscription.STATUS_EXPIRED, Subscription.STATUS_CANCELLED):
        return 'expired_cancelled'
    return 'trial'


def _serialize_company(org):
    sub = _latest_subscription(org)
    return {
        'id': str(org.id),
        'name': org.name,
        'email': org.email,
        'phone': org.phone,
        'size': org.size,
        'industry': org.industry,
        'status': org.status,
        'bucket': _bucket_for(org),
        'suspendedAt': org.suspended_at.isoformat() if org.suspended_at else None,
        'suspendedReason': org.suspended_reason,
        'createdAt': org.created_at.isoformat(),
        'currentSubscription': _serialize_subscription_summary(sub) if sub else None,
    }


def _serialize_subscription_summary(sub):
    return {
        'id': str(sub.id),
        'plan': sub.plan,
        'status': sub.status,
        'amount': float(sub.amount),
        'currency': sub.currency,
        'startDate': sub.start_date.isoformat() if sub.start_date else None,
        'endDate': sub.end_date.isoformat() if sub.end_date else None,
    }


def _company_recipient_emails(org):
    admins = UserProfile.objects.filter(
        organization=org, account_type=UserProfile.ACCOUNT_TYPE_COMPANY, employee__isnull=True,
    ).select_related('user')
    emails = [p.user.email for p in admins if p.user.email]
    return emails or ([org.email] if org.email else [])


def _notify_company_status_change(org, status, reason):
    recipients = _company_recipient_emails(org)
    if not recipients:
        return
    suspended = status == Organization.STATUS_SUSPENDED
    status_label = 'suspended' if suspended else 'reactivated'
    status_message = (
        'You will not be able to sign in until the workspace is reactivated. '
        'Contact support if you believe this is a mistake.'
        if suspended else
        'You can sign in and continue using your workspace as normal.'
    )
    try:
        get_email_service().send_mail(
            subject=f'Your Workiva workspace has been {status_label}',
            body=(
                f'The {org.name} workspace has been {status_label}.'
                + (f' Reason: {reason}' if reason else '')
                + f' {status_message}'
            ),
            html_body=render_email_template(
                'emails/company_status_changed.html',
                {
                    'email_title': f'Workspace {status_label}',
                    'email_eyebrow': 'Account Status',
                    'email_heading': f'Your workspace has been {status_label}',
                    'organization_name': org.name,
                    'status_label': status_label,
                    'status_message': status_message,
                    'reason': reason,
                },
            ),
            to_emails=recipients,
        )
    except Exception:
        logger.exception('Failed to send company status change email for org=%s status=%s', org.id, status)


def _base_queryset():
    return Organization.objects.prefetch_related(
        Prefetch('subscriptions', queryset=Subscription.objects.order_by('-created_at'), to_attr='_subs')
    ).order_by('-created_at')


@require_GET
def company_list_view(request):
    try:
        require_superuser(request)
        orgs = list(_base_queryset())

        search = request.GET.get('search', '').strip().lower()
        if search:
            orgs = [o for o in orgs if search in o.name.lower() or search in o.email.lower()]

        bucket = request.GET.get('status', '').strip()
        if bucket:
            valid_buckets = {'active', 'trial', 'suspended', 'expired_cancelled'}
            if bucket not in valid_buckets:
                raise ValidationError('status must be one of active, trial, suspended, expired_cancelled.')
            orgs = [o for o in orgs if _bucket_for(o) == bucket]

        total = len(orgs)
        page_size = int(request.GET.get('page_size') or 20)
        page = int(request.GET.get('page') or 1)
        start = (page - 1) * page_size
        page_items = orgs[start:start + page_size]

        return JsonResponse({'success': True, 'data': {
            'companies': [_serialize_company(o) for o in page_items],
            'pagination': {
                'page': page, 'page_size': page_size, 'total_items': total,
                'total_pages': max(1, (total + page_size - 1) // page_size),
            },
        }})
    except AppError as exc:
        return error_response(exc)


@require_GET
def company_detail_view(request, org_id):
    try:
        require_superuser(request)
        org = _base_queryset().filter(id=org_id).first()
        if org is None:
            raise NotFoundError('Company not found.')

        admins = UserProfile.objects.filter(
            organization=org, account_type=UserProfile.ACCOUNT_TYPE_COMPANY, employee__isnull=True,
        ).select_related('user')
        employee_count = org.employees.count()
        subscriptions = getattr(org, '_subs', [])

        return JsonResponse({'success': True, 'data': {
            'company': _serialize_company(org),
            'employeeCount': employee_count,
            'admins': [
                {'id': p.user_id, 'email': p.user.email, 'fullName': p.full_name}
                for p in admins
            ],
            'subscriptions': [_serialize_subscription_summary(s) for s in subscriptions],
        }})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['PATCH'])
def company_status_view(request, org_id):
    try:
        user = require_superuser(request)
        org = Organization.objects.filter(id=org_id).first()
        if org is None:
            raise NotFoundError('Company not found.')

        payload = load_json(request)
        status = str(payload.get('status', '')).strip()
        if status not in dict(Organization.STATUS_CHOICES):
            raise ValidationError('status must be active or suspended.')
        reason = str(payload.get('reason', '')).strip()
        previous_status = org.status

        org.status = status
        org.suspended_reason = reason if status == Organization.STATUS_SUSPENDED else ''
        org.suspended_at = timezone.now() if status == Organization.STATUS_SUSPENDED else None
        org.save(update_fields=['status', 'suspended_reason', 'suspended_at', 'updated_at'])

        if status != previous_status:
            _notify_company_status_change(org, status, reason)

        record_audit_event_safely(
            organization=org, actor=user, request=request,
            action='platform.company_status_changed', category='platform',
            description=f'{user.email} set {org.name} status to {status}.' + (f' Reason: {reason}' if reason else ''),
            resource_type='organization', resource_id=org.id,
        )

        org = _base_queryset().filter(id=org.id).first()
        return JsonResponse({'success': True, 'data': {'company': _serialize_company(org)}})
    except AppError as exc:
        return error_response(exc)
