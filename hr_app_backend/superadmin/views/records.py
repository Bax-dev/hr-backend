from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.employees.models import Employee
from hr_app_backend.employees.serializers.employee import serialize_employee
from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.pagination import paginated_data

from .helpers import require_superuser


def _serialize_record(employee):
    payload = serialize_employee(employee)
    payload['organization'] = {'id': str(employee.organization_id), 'name': employee.organization.name}
    payload['isDeleted'] = employee.is_deleted
    payload['deletedAt'] = employee.deleted_at.isoformat() if employee.deleted_at else None
    return payload


def _filtered(queryset, request):
    organization_id = request.GET.get('organization_id', '').strip()
    if organization_id:
        queryset = queryset.filter(organization_id=organization_id)
    search = request.GET.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search)
        )
    return queryset


@require_GET
def employee_records_view(request):
    try:
        require_superuser(request)
        employees = _filtered(Employee.objects.select_related('organization').order_by('-created_at'), request)
        data = paginated_data(request, employees, _serialize_record, key='employees', default_page_size=25)
        return JsonResponse({'success': True, 'data': data})
    except AppError as exc:
        return error_response(exc)


@require_GET
def archived_records_view(request):
    try:
        require_superuser(request)
        employees = _filtered(
            Employee.all_objects.filter(is_deleted=True).select_related('organization').order_by('-deleted_at'),
            request,
        )
        data = paginated_data(request, employees, _serialize_record, key='employees', default_page_size=25)
        return JsonResponse({'success': True, 'data': data})
    except AppError as exc:
        return error_response(exc)
