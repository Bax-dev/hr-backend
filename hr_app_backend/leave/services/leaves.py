import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from hr_app_backend.utils import local_now
from hr_app_backend.utils.errors import NotFoundError, PermissionDeniedError, ValidationError

from hr_app_backend.authentication.models import UserProfile
from hr_app_backend.employees.models import Employee

from ..models import LeaveRequest

REQUIRED_FIELDS = ('employee_id', 'leave_type', 'start_date', 'end_date', 'reason')


def _require_organization(user):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is None:
        raise PermissionDeniedError('A company account is required to manage leave requests.')
    return organization


def _clean_date(value, field_name):
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError(f'{field_name} must be an ISO date (YYYY-MM-DD).') from exc


def _clean_status(value):
    if not value:
        return LeaveRequest.STATUS_PENDING
    status = str(value).strip().lower().replace(' ', '_').replace('-', '_')
    valid = {choice for choice, _ in LeaveRequest.STATUSES}
    if status not in valid:
        raise ValidationError(f'Status must be one of: {", ".join(sorted(valid))}.')
    return status


def _clean_leave_type(value):
    leave_type = str(value or '').strip().title()
    valid = {choice for choice, _ in LeaveRequest.LEAVE_TYPES}
    if leave_type not in valid:
        raise ValidationError(f'Leave type must be one of: {", ".join(sorted(valid))}.')
    return leave_type


def _calculate_days(start_date, end_date):
    if end_date < start_date:
        raise ValidationError('End date cannot be earlier than start date.')
    return (end_date - start_date).days + 1


def _get_employee(organization, employee_pk):
    try:
        return Employee.objects.get(organization=organization, pk=employee_pk)
    except (Employee.DoesNotExist, DjangoValidationError, ValueError) as exc:
        raise NotFoundError('Employee not found.') from exc


def _resolve_employee(user, organization, data):
    """Determine which employee a leave request is for.

    Individual accounts can only file leave for themselves, so the employee is
    taken from their linked profile rather than trusting the client-supplied id
    (which is the integer user id, not the employee UUID).
    """
    profile = getattr(user, 'profile', None)
    account_type = getattr(profile, 'account_type', None)

    if account_type == UserProfile.ACCOUNT_TYPE_INDIVIDUAL:
        employee = getattr(profile, 'employee', None)
        if employee is None:
            raise ValidationError('Your account is not linked to an employee record yet.')
        return employee

    return _get_employee(organization, data['employee_id'])


def list_leaves(user, status=None, employee_id=None):
    organization = _require_organization(user)
    queryset = LeaveRequest.objects.select_related('employee').filter(organization=organization)

    if status:
        queryset = queryset.filter(status=_clean_status(status))
    if employee_id:
        queryset = queryset.filter(employee_id=employee_id)

    return queryset


def get_leave(user, leave_pk):
    organization = _require_organization(user)
    try:
        return LeaveRequest.objects.select_related('employee').get(organization=organization, pk=leave_pk)
    except LeaveRequest.DoesNotExist as exc:
        raise NotFoundError('Leave request not found.') from exc


@transaction.atomic
def create_leave(user, data):
    organization = _require_organization(user)

    for field in REQUIRED_FIELDS:
        if not (data.get(field) or '').strip():
            raise ValidationError(f'{field.replace("_", " ").capitalize()} is required.')

    employee = _resolve_employee(user, organization, data)
    start_date = _clean_date(data['start_date'], 'Start date')
    end_date = _clean_date(data['end_date'], 'End date')

    return LeaveRequest.objects.create(
        organization=organization,
        employee=employee,
        leave_type=_clean_leave_type(data['leave_type']),
        start_date=start_date,
        end_date=end_date,
        days=_calculate_days(start_date, end_date),
        reason=(data.get('reason') or '').strip(),
        status=_clean_status(data.get('status')),
        reviewed_at=local_now() if _clean_status(data.get('status')) != LeaveRequest.STATUS_PENDING else None,
    )


@transaction.atomic
def update_leave(user, leave_pk, data):
    leave = get_leave(user, leave_pk)

    if 'employee_id' in data:
        leave.employee = _get_employee(leave.organization, data['employee_id'])

    if 'leave_type' in data:
        leave.leave_type = _clean_leave_type(data['leave_type'])

    start_date = leave.start_date
    end_date = leave.end_date
    if 'start_date' in data:
        start_date = _clean_date(data['start_date'], 'Start date')
        leave.start_date = start_date
    if 'end_date' in data:
        end_date = _clean_date(data['end_date'], 'End date')
        leave.end_date = end_date
    if 'start_date' in data or 'end_date' in data:
        leave.days = _calculate_days(start_date, end_date)

    if 'reason' in data:
        reason = (data['reason'] or '').strip()
        if not reason:
            raise ValidationError('Reason cannot be empty.')
        leave.reason = reason

    if 'status' in data:
        leave.status = _clean_status(data['status'])
        leave.reviewed_at = None if leave.status == LeaveRequest.STATUS_PENDING else local_now()

    leave.save()
    return leave
