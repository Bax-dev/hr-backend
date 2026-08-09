from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.billing.models import Subscription
from hr_app_backend.utils.errors import AppError, ValidationError
from hr_app_backend.utils.pagination import paginated_data

from .helpers import require_superuser

BUCKET_FILTERS = {
    'active': Q(status=Subscription.STATUS_ACTIVE) & ~Q(plan=Subscription.PLAN_FREE_TRIAL),
    'trial': Q(plan=Subscription.PLAN_FREE_TRIAL, status=Subscription.STATUS_ACTIVE),
    'expired_cancelled': Q(status__in=[Subscription.STATUS_EXPIRED, Subscription.STATUS_CANCELLED]),
}


def _serialize_subscription(sub):
    return {
        'id': str(sub.id),
        'organization': {
            'id': str(sub.organization_id), 'name': sub.organization.name,
        } if sub.organization_id else None,
        'plan': sub.plan,
        'provider': sub.provider,
        'status': sub.status,
        'amount': float(sub.amount),
        'currency': sub.currency,
        'startDate': sub.start_date.isoformat() if sub.start_date else None,
        'endDate': sub.end_date.isoformat() if sub.end_date else None,
        'paidAt': sub.paid_at.isoformat() if sub.paid_at else None,
        'createdAt': sub.created_at.isoformat(),
    }


@require_GET
def subscription_list_view(request):
    try:
        require_superuser(request)
        subs = Subscription.objects.select_related('organization', 'created_by')

        bucket = request.GET.get('bucket', '').strip()
        if bucket:
            if bucket not in BUCKET_FILTERS:
                raise ValidationError('bucket must be one of active, trial, expired_cancelled.')
            subs = subs.filter(BUCKET_FILTERS[bucket])

        plan = request.GET.get('plan', '').strip()
        if plan:
            subs = subs.filter(plan=plan)

        search = request.GET.get('search', '').strip()
        if search:
            subs = subs.filter(Q(organization__name__icontains=search) | Q(reference__icontains=search))

        data = paginated_data(request, subs, _serialize_subscription, key='subscriptions', default_page_size=25)
        return JsonResponse({'success': True, 'data': data})
    except AppError as exc:
        return error_response(exc)


@require_GET
def plan_summary_view(request):
    try:
        require_superuser(request)
        active_subs = Subscription.objects.filter(status=Subscription.STATUS_ACTIVE)
        counts = {
            row['plan']: row for row in active_subs.values('plan').annotate(
                subscriberCount=Count('id'), revenue=Sum('amount'),
            )
        }
        plans = [
            {
                'plan': value,
                'label': label,
                'subscriberCount': counts.get(value, {}).get('subscriberCount', 0),
                'revenue': float(counts.get(value, {}).get('revenue') or 0),
            }
            for value, label in Subscription.PLAN_CHOICES
        ]
        return JsonResponse({'success': True, 'data': {'plans': plans}})
    except AppError as exc:
        return error_response(exc)
