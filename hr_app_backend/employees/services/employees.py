import datetime
import decimal

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q

from hr_app_backend.utils.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

from ..models import Employee

REQUIRED_FIELDS = ('first_name', 'last_name', 'email')


def _require_organization(user):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is None:
        raise PermissionDeniedError('A company account is required to manage employees.')
    return organization


def _validate_email_address(email):
    try:
        validate_email(email)
    except DjangoValidationError as exc:
        raise ValidationError('A valid email address is required.') from exc


def _clean_hire_date(value):
    if value in (None, ''):
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError('Hire date must be an ISO date (YYYY-MM-DD).') from exc


def _clean_salary(value):
    if value in (None, ''):
        return None
    try:
        return decimal.Decimal(str(value))
    except decimal.InvalidOperation as exc:
        raise ValidationError('Salary must be a number.') from exc


def _clean_status(value):
    if not value:
        return Employee.STATUS_ACTIVE
    status = str(value).strip().lower().replace(' ', '_').replace('-', '_')
    valid = {choice for choice, _ in Employee.STATUSES}
    if status not in valid:
        raise ValidationError(f'Status must be one of: {", ".join(sorted(valid))}.')
    return status


def _next_employee_id(organization):
    count = Employee.objects.filter(organization=organization).count()
    while True:
        count += 1
        candidate = f'EMP-{count:04d}'
        if not Employee.objects.filter(organization=organization, employee_id=candidate).exists():
            return candidate


def list_employees(user, search=None, department=None, status=None):
    organization = _require_organization(user)
    queryset = Employee.objects.filter(organization=organization)

    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(employee_id__icontains=search)
        )
    if department:
        queryset = queryset.filter(department__iexact=department)
    if status:
        queryset = queryset.filter(status=_clean_status(status))

    return queryset


def get_employee(user, employee_pk):
    organization = _require_organization(user)
    try:
        return Employee.objects.get(organization=organization, pk=employee_pk)
    except Employee.DoesNotExist as exc:
        raise NotFoundError('Employee not found.') from exc


@transaction.atomic
def create_employee(user, data):
    organization = _require_organization(user)

    for field in REQUIRED_FIELDS:
        if not (data.get(field) or '').strip():
            raise ValidationError(f'{field.replace("_", " ").capitalize()} is required.')

    email = data['email'].strip().lower()
    _validate_email_address(email)

    if Employee.objects.filter(organization=organization, email=email).exists():
        raise ConflictError('An employee with this email already exists.')

    employee_id = (data.get('employee_id') or '').strip() or _next_employee_id(organization)
    if Employee.objects.filter(organization=organization, employee_id=employee_id).exists():
        raise ConflictError('An employee with this employee ID already exists.')

    return Employee.objects.create(
        organization=organization,
        employee_id=employee_id,
        first_name=data['first_name'].strip(),
        last_name=data['last_name'].strip(),
        email=email,
        phone=(data.get('phone') or '').strip(),
        department=(data.get('department') or '').strip(),
        position=(data.get('position') or '').strip(),
        status=_clean_status(data.get('status')),
        gender=(data.get('gender') or '').strip(),
        country=(data.get('country') or '').strip(),
        hire_date=_clean_hire_date(data.get('hire_date')),
        salary=_clean_salary(data.get('salary')),
        avatar=(data.get('avatar') or '').strip(),
        manager=(data.get('manager') or '').strip(),
    )


@transaction.atomic
def update_employee(user, employee_pk, data):
    employee = get_employee(user, employee_pk)

    if 'email' in data:
        email = (data['email'] or '').strip().lower()
        _validate_email_address(email)
        duplicate = Employee.objects.filter(
            organization=employee.organization, email=email
        ).exclude(pk=employee.pk)
        if duplicate.exists():
            raise ConflictError('An employee with this email already exists.')
        employee.email = email

    if 'employee_id' in data:
        employee_id = (data['employee_id'] or '').strip()
        if not employee_id:
            raise ValidationError('Employee ID cannot be empty.')
        duplicate = Employee.objects.filter(
            organization=employee.organization, employee_id=employee_id
        ).exclude(pk=employee.pk)
        if duplicate.exists():
            raise ConflictError('An employee with this employee ID already exists.')
        employee.employee_id = employee_id

    for field in ('first_name', 'last_name'):
        if field in data:
            value = (data[field] or '').strip()
            if not value:
                raise ValidationError(f'{field.replace("_", " ").capitalize()} cannot be empty.')
            setattr(employee, field, value)

    for field in ('phone', 'department', 'position', 'gender', 'country', 'avatar', 'manager'):
        if field in data:
            setattr(employee, field, (data[field] or '').strip())

    if 'status' in data:
        employee.status = _clean_status(data['status'])
    if 'hire_date' in data:
        employee.hire_date = _clean_hire_date(data['hire_date'])
    if 'salary' in data:
        employee.salary = _clean_salary(data['salary'])

    employee.save()
    return employee


def delete_employee(user, employee_pk):
    employee = get_employee(user, employee_pk)
    employee.delete()
