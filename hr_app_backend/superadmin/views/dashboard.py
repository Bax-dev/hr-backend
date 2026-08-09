from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from hr_app_backend.audit_logs.models import AuditLog
from hr_app_backend.audit_logs.serializers import serialize_audit_log
from hr_app_backend.authentication.models import UserProfile
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.billing.models import Subscription
from hr_app_backend.employees.models import Employee
from hr_app_backend.utils.errors import AppError

from .companies import _base_queryset, _bucket_for, _serialize_company
from .helpers import require_superuser

REVENUE_MONTHS = 6
MOST_ACTIVE_WINDOW_DAYS = 30
MOST_ACTIVE_LIMIT = 5

User = get_user_model()


def _month_start(anchor, months_ago):
    year, month = anchor.year, anchor.month - months_ago
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _monthly_revenue():
    today = timezone.localdate()
    months = [_month_start(today, i) for i in range(REVENUE_MONTHS - 1, -1, -1)]
    earliest = months[0]

    rows = (
        Subscription.objects.filter(paid_at__date__gte=earliest)
        .annotate(month=TruncMonth('paid_at'))
        .values('month')
        .annotate(total=Sum('amount'))
    )
    totals_by_month = {row['month'].date(): float(row['total'] or 0) for row in rows}

    return [{'month': m.strftime('%Y-%m'), 'revenue': totals_by_month.get(m, 0.0)} for m in months]


def _most_active_companies():
    since = timezone.now() - timedelta(days=MOST_ACTIVE_WINDOW_DAYS)
    rows = (
        AuditLog.objects.filter(created_at__gte=since)
        .values('organization_id', 'organization__name')
        .annotate(eventCount=Count('id'))
        .order_by('-eventCount')[:MOST_ACTIVE_LIMIT]
    )
    return [
        {'id': str(row['organization_id']), 'name': row['organization__name'], 'eventCount': row['eventCount']}
        for row in rows
        if row['organization_id']
    ]


@require_GET
def dashboard_overview_view(request):
    try:
        require_superuser(request)

        orgs = list(_base_queryset())
        buckets = {'active': 0, 'trial': 0, 'suspended': 0, 'expired_cancelled': 0}
        for org in orgs:
            buckets[_bucket_for(org)] += 1

        sub_status_counts = {
            row['status']: row['count']
            for row in Subscription.objects.values('status').annotate(count=Count('id'))
        }

        recent_signups = sorted(orgs, key=lambda o: o.created_at, reverse=True)[:5]
        recent_audit_events = AuditLog.objects.select_related('actor', 'organization').order_by('-created_at')[:5]

        today = timezone.localdate()
        this_month_start = today.replace(day=1)
        last_month_start = _month_start(today, 1)

        monthly_revenue = _monthly_revenue()
        current_month_revenue = monthly_revenue[-1]['revenue'] if monthly_revenue else 0.0
        paying_companies = buckets['active']

        return JsonResponse({'success': True, 'data': {
            'companies': {
                'total': len(orgs),
                'active': buckets['active'],
                'trial': buckets['trial'],
                'suspended': buckets['suspended'],
                'expiredCancelled': buckets['expired_cancelled'],
            },
            'accounts': {
                'totalRegistered': User.objects.count(),
                'newThisMonth': User.objects.filter(date_joined__date__gte=this_month_start).count(),
                'newLastMonth': User.objects.filter(
                    date_joined__date__gte=last_month_start, date_joined__date__lt=this_month_start
                ).count(),
            },
            'users': {
                'total': UserProfile.objects.count(),
                'employees': UserProfile.objects.filter(
                    account_type=UserProfile.ACCOUNT_TYPE_COMPANY, employee__isnull=False
                ).count(),
                'companyAdmins': UserProfile.objects.filter(
                    account_type=UserProfile.ACCOUNT_TYPE_COMPANY, employee__isnull=True
                ).count(),
                'individuals': UserProfile.objects.filter(account_type=UserProfile.ACCOUNT_TYPE_INDIVIDUAL).count(),
            },
            'employees': {'total': Employee.objects.count()},
            'subscriptions': {
                'active': sub_status_counts.get(Subscription.STATUS_ACTIVE, 0),
                'pending': sub_status_counts.get(Subscription.STATUS_PENDING, 0),
                'failed': sub_status_counts.get(Subscription.STATUS_FAILED, 0),
                'cancelled': sub_status_counts.get(Subscription.STATUS_CANCELLED, 0),
                'expired': sub_status_counts.get(Subscription.STATUS_EXPIRED, 0),
            },
            'revenue': {
                'monthly': monthly_revenue,
                'currentMonthTotal': current_month_revenue,
                'averageRevenuePerCompany': round(current_month_revenue / paying_companies, 2) if paying_companies else 0.0,
            },
            'mostActiveCompanies': _most_active_companies(),
            'recentSignups': [_serialize_company(o) for o in recent_signups],
            'recentActivity': [serialize_audit_log(log) for log in recent_audit_events],
        }})
    except AppError as exc:
        return error_response(exc)
