from datetime import datetime
from decimal import Decimal

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.employees.models import Employee
from hr_app_backend.employees.views.helpers import require_user
from hr_app_backend.utils.errors import AppError, NotFoundError, ValidationError

from .models import Announcement, PayrollRecord, PlatformRecord

PLATFORM_MODULE_CONFIG = {
    'approvals': {'list_key': 'approvals', 'item_key': 'approval'},
    'communications': {'list_key': 'communications', 'item_key': 'communication'},
    'analytics': {'list_key': 'reports', 'item_key': 'report'},
    'compliance': {'list_key': 'items', 'item_key': 'item'},
    'ai-features': {'list_key': 'features', 'item_key': 'feature'},
    'notifications': {'list_key': 'workflows', 'item_key': 'workflow'},
    'integrations': {'list_key': 'integrations', 'item_key': 'integration'},
    'admin-controls': {'list_key': 'controls', 'item_key': 'control'},
    'dashboards': {'list_key': 'dashboards', 'item_key': 'dashboard'},
}


def _organization_for(request):
    user = require_user(request)
    organization = getattr(getattr(user, 'profile', None), 'organization', None)
    if organization is None:
        raise ValidationError('Your account is not linked to an organization.')
    return user, organization


def _announcement_payload(data):
    title = str(data.get('title', '')).strip()
    content = str(data.get('content', '')).strip()
    priority = str(data.get('priority', 'Normal')).strip() or 'Normal'
    if len(title) < 3:
        raise ValidationError('Title is required.')
    if len(content) < 10:
        raise ValidationError('Content must be at least 10 characters.')
    return {'title': title, 'content': content, 'priority': priority}


def _serialize_announcement(announcement):
    return {
        'id': announcement.id,
        'title': announcement.title,
        'content': announcement.content,
        'author': announcement.author,
        'createdAt': announcement.created_at.isoformat(),
        'priority': announcement.priority,
    }


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def announcements_view(request):
    try:
        user, organization = _organization_for(request)
        if request.method == 'GET':
            records = Announcement.objects.filter(organization=organization)
            return JsonResponse([_serialize_announcement(record) for record in records], safe=False)

        payload = _announcement_payload(parse_json_body(request))
        author = getattr(getattr(user, 'profile', None), 'full_name', '') or user.get_full_name() or user.email
        announcement = Announcement.objects.create(
            organization=organization,
            author=author,
            **payload,
        )
        return JsonResponse(_serialize_announcement(announcement), status=201)
    except AppError as exc:
        return error_response(exc)


def _month_value(raw):
    value = (raw or '').strip()
    if not value:
        return timezone.now().date().strftime('%Y-%m')
    try:
        datetime.strptime(value, '%Y-%m')
    except ValueError as exc:
        raise ValidationError('Month must be in YYYY-MM format.') from exc
    return value


def _serialize_payroll_record(record):
    return {
        'id': str(record.id),
        'employee_id': str(record.employee_id),
        'employee_name': f'{record.employee.first_name} {record.employee.last_name}'.strip(),
        'department': record.department,
        'month': record.month,
        'base_salary': float(record.base_salary),
        'bonuses': float(record.bonuses),
        'deductions': float(record.deductions),
        'net_pay': float(record.net_pay),
        'status': record.status,
        'processed_at': record.processed_at.isoformat() if record.processed_at else None,
    }


def _payroll_summary(month, records):
    total_payroll = sum(record.net_pay for record in records)
    total_bonuses = sum(record.bonuses for record in records)
    total_deductions = sum(record.deductions for record in records)
    total_employees = len(records)
    average_salary = (total_payroll / total_employees) if total_employees else Decimal('0')
    return {
        'month': month,
        'total_payroll': float(total_payroll),
        'average_salary': float(average_salary),
        'total_bonuses': float(total_bonuses),
        'total_deductions': float(total_deductions),
        'total_employees': total_employees,
    }


def _build_payroll_record(organization, employee, month):
    base_salary = employee.salary or Decimal('0')
    bonuses = Decimal('3500') if employee.department.strip().lower() == 'engineering' else Decimal('1500')
    deductions = (base_salary * Decimal('0.04')).quantize(Decimal('0.01'))
    net_pay = base_salary + bonuses - deductions
    return PayrollRecord.objects.create(
        organization=organization,
        employee=employee,
        department=employee.department,
        month=month,
        base_salary=base_salary,
        bonuses=bonuses,
        deductions=deductions,
        net_pay=net_pay,
        status=PayrollRecord.STATUS_PROCESSING,
    )


@require_http_methods(['GET'])
def payroll_records_view(request):
    try:
        _, organization = _organization_for(request)
        month = _month_value(request.GET.get('month'))
        records = list(
            PayrollRecord.objects.filter(organization=organization, month=month).select_related('employee')
        )
        return JsonResponse({'success': True, 'data': {'records': [_serialize_payroll_record(record) for record in records]}})
    except AppError as exc:
        return error_response(exc)


@require_http_methods(['GET'])
def payroll_summary_view(request):
    try:
        _, organization = _organization_for(request)
        month = _month_value(request.GET.get('month'))
        records = list(PayrollRecord.objects.filter(organization=organization, month=month))
        return JsonResponse({'success': True, 'data': {'summary': _payroll_summary(month, records)}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
def payroll_run_view(request):
    try:
        _, organization = _organization_for(request)
        month = _month_value(parse_json_body(request).get('month'))
        employees = list(
            Employee.objects.filter(organization=organization).exclude(status=Employee.STATUS_TERMINATED)
        )
        if not employees:
            raise ValidationError('No employees are available for payroll.')

        existing_ids = set(
            PayrollRecord.objects.filter(organization=organization, month=month).values_list('employee_id', flat=True)
        )
        for employee in employees:
            if employee.id not in existing_ids:
                _build_payroll_record(organization, employee, month)

        records = list(
            PayrollRecord.objects.filter(organization=organization, month=month).select_related('employee')
        )
        return JsonResponse({
            'success': True,
            'message': 'Payroll run completed successfully.',
            'data': {'summary': _payroll_summary(month, records)},
        })
    except AppError as exc:
        return error_response(exc)


def _serialize_platform_record(record):
    payload = dict(record.payload)
    payload['id'] = str(record.id)
    if record.module == 'approvals':
        payload['updatedAt'] = record.updated_at.isoformat() if record.updated_at else None
    return payload


def _module_record(module, organization, record_pk):
    try:
        return PlatformRecord.objects.get(module=module, organization=organization, pk=record_pk)
    except PlatformRecord.DoesNotExist as exc:
        raise NotFoundError('Record not found.') from exc


def _list_response(module, organization):
    config = PLATFORM_MODULE_CONFIG[module]
    records = PlatformRecord.objects.filter(module=module, organization=organization)
    return JsonResponse({
        'success': True,
        'data': {config['list_key']: [_serialize_platform_record(record) for record in records]},
    })


def _create_response(module, organization, payload):
    config = PLATFORM_MODULE_CONFIG[module]
    record = PlatformRecord.objects.create(module=module, organization=organization, payload=payload)
    return JsonResponse({'success': True, 'data': {config['item_key']: _serialize_platform_record(record)}}, status=201)


def _detail_response(module, organization, record_pk, payload=None):
    config = PLATFORM_MODULE_CONFIG[module]
    record = _module_record(module, organization, record_pk)
    if payload is not None:
        updated = dict(record.payload)
        updated.update(payload)
        record.payload = updated
        record.save(update_fields=['payload', 'updated_at'])
    return JsonResponse({'success': True, 'data': {config['item_key']: _serialize_platform_record(record)}})


def _delete_response(module, organization, record_pk):
    _module_record(module, organization, record_pk).delete()
    return JsonResponse({'success': True, 'message': 'Record deleted successfully.'})


def _collection_view(request, module):
    _, organization = _organization_for(request)
    if request.method == 'GET':
        return _list_response(module, organization)
    return _create_response(module, organization, parse_json_body(request))


def _detail_view(request, module, record_pk):
    _, organization = _organization_for(request)
    if request.method == 'DELETE':
        return _delete_response(module, organization, record_pk)
    return _detail_response(module, organization, record_pk, parse_json_body(request))


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def approvals_view(request):
    try:
        return _collection_view(request, 'approvals')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def approval_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'approvals', record_pk)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def communications_view(request):
    try:
        return _collection_view(request, 'communications')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def communication_detail_view(request, record_pk, module='communications'):
    try:
        return _detail_view(request, module, record_pk)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def analytics_view(request):
    try:
        return _collection_view(request, 'analytics')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def compliance_view(request):
    try:
        return _collection_view(request, 'compliance')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def compliance_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'compliance', record_pk)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def ai_features_view(request):
    try:
        return _collection_view(request, 'ai-features')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def notifications_view(request):
    try:
        return _collection_view(request, 'notifications')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def notification_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'notifications', record_pk)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def integrations_view(request):
    try:
        return _collection_view(request, 'integrations')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def integration_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'integrations', record_pk)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def admin_controls_view(request):
    try:
        return _collection_view(request, 'admin-controls')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def dashboards_view(request):
    try:
        return _collection_view(request, 'dashboards')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def dashboard_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'dashboards', record_pk)
    except AppError as exc:
        return error_response(exc)
