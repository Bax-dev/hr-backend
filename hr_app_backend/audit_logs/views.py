from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from hr_app_backend.authentication.services import get_user_by_token
from hr_app_backend.authentication.views.helpers import error_response, token_from_request
from hr_app_backend.utils.errors import AppError, AuthenticationError, PermissionDeniedError, ValidationError
from hr_app_backend.utils.pagination import paginate_queryset

from .models import AuditLog


def _serialize(log):
    return {
        'id': str(log.id), 'action': log.action, 'category': log.category,
        'description': log.description, 'status': log.status,
        'actor': {'id': str(log.actor_id) if log.actor_id else None, 'name': log.actor_name, 'email': log.actor_email},
        'resource': {'type': log.resource_type, 'id': log.resource_id},
        'ipAddress': log.ip_address, 'userAgent': log.user_agent, 'requestId': log.request_id,
        'metadata': log.metadata, 'createdAt': log.created_at.isoformat(),
    }


@require_GET
def audit_log_list_view(request):
    try:
        user = get_user_by_token(token_from_request(request))
        if user is None:
            raise AuthenticationError('Authentication credentials were not provided or are invalid.')
        profile = getattr(user, 'profile', None)
        if profile is None or profile.account_type != profile.ACCOUNT_TYPE_COMPANY or not profile.organization_id:
            raise PermissionDeniedError('Only company administrators can view audit logs.')

        logs = AuditLog.objects.filter(organization_id=profile.organization_id).select_related('actor')
        search = request.GET.get('search', '').strip()
        category = request.GET.get('category', '').strip()
        status = request.GET.get('status', '').strip()
        action = request.GET.get('action', '').strip()
        if search:
            logs = logs.filter(Q(description__icontains=search) | Q(actor_name__icontains=search) |
                               Q(actor_email__icontains=search) | Q(action__icontains=search) |
                               Q(resource_id__icontains=search))
        if category:
            logs = logs.filter(category=category)
        if action:
            logs = logs.filter(action=action)
        if status:
            if status not in dict(AuditLog.STATUS_CHOICES):
                raise ValidationError('Status must be success or failure.')
            logs = logs.filter(status=status)

        items, pagination = paginate_queryset(request, logs, default_page_size=25)
        categories = list(AuditLog.objects.filter(organization_id=profile.organization_id)
                          .values_list('category', flat=True).distinct().order_by('category'))
        return JsonResponse({'success': True, 'data': {
            'logs': [_serialize(log) for log in items], 'pagination': pagination, 'categories': categories,
        }})
    except AppError as exc:
        return error_response(exc)
