from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from hr_app_backend.audit_logs.models import AuditLog
from hr_app_backend.audit_logs.serializers import serialize_audit_log
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError, ValidationError
from hr_app_backend.utils.pagination import paginate_queryset

from .helpers import require_superuser


@require_GET
def superadmin_audit_log_list_view(request):
    try:
        require_superuser(request)
        logs = AuditLog.objects.select_related('actor', 'organization')

        organization_id = request.GET.get('organization_id', '').strip()
        if organization_id:
            logs = logs.filter(organization_id=organization_id)

        search = request.GET.get('search', '').strip()
        category = request.GET.get('category', '').strip()
        status = request.GET.get('status', '').strip()
        action = request.GET.get('action', '').strip()
        if search:
            logs = logs.filter(
                Q(description__icontains=search) | Q(actor_name__icontains=search) |
                Q(actor_email__icontains=search) | Q(action__icontains=search) |
                Q(resource_id__icontains=search) | Q(organization__name__icontains=search)
            )
        if category:
            logs = logs.filter(category=category)
        if action:
            logs = logs.filter(action=action)
        if status:
            if status not in dict(AuditLog.STATUS_CHOICES):
                raise ValidationError('Status must be success or failure.')
            logs = logs.filter(status=status)

        items, pagination = paginate_queryset(request, logs, default_page_size=25)
        categories = list(AuditLog.objects.values_list('category', flat=True).distinct().order_by('category'))
        return JsonResponse({'success': True, 'data': {
            'logs': [serialize_audit_log(log) for log in items], 'pagination': pagination, 'categories': categories,
        }})
    except AppError as exc:
        return error_response(exc)
