from django.db import transaction
import re

from hr_app_backend.utils.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from hr_app_backend.employees.models import Employee
from hr_app_backend.authentication.models import UserProfile

from ..models import Department


def _require_organization(user):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is None:
        raise PermissionDeniedError('A company account is required to manage departments.')
    if getattr(profile, 'account_type', None) != UserProfile.ACCOUNT_TYPE_COMPANY:
        raise PermissionDeniedError('Only company administrators can manage departments.')
    return organization


def _clean_name(value):
    name = (value or '').strip()
    if len(name) < 2:
        raise ValidationError('Department name is required.')
    return name


def _clean_manager(value):
    manager = (value or '').strip()
    if len(manager) < 2:
        raise ValidationError('Manager name is required.')
    return manager


def _clean_color(value):
    color = (value or '').strip() or '#2563eb'
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValidationError('A valid department color is required.')
    return color.lower()


def list_departments(user):
    organization = _require_organization(user)
    departments = Department.objects.filter(organization=organization).order_by('name')
    employees = Employee.objects.filter(organization=organization).values_list('department', flat=True)
    counts = {}
    for department_name in employees:
        normalized = (department_name or '').strip().lower()
        if not normalized:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    return departments, counts


def get_department(user, department_pk):
    organization = _require_organization(user)
    try:
        return Department.objects.get(organization=organization, pk=department_pk)
    except Department.DoesNotExist as exc:
        raise NotFoundError('Department not found.') from exc


@transaction.atomic
def create_department(user, data):
    organization = _require_organization(user)
    name = _clean_name(data.get('name'))
    manager = _clean_manager(data.get('manager'))
    color = _clean_color(data.get('color'))

    if Department.objects.filter(organization=organization, name__iexact=name).exists():
        raise ConflictError('A department with this name already exists.')

    return Department.objects.create(
        organization=organization,
        name=name,
        manager=manager,
        color=color,
    )


@transaction.atomic
def update_department(user, department_pk, data):
    department = get_department(user, department_pk)

    if 'name' in data:
        name = _clean_name(data.get('name'))
        duplicate = Department.objects.filter(
            organization=department.organization,
            name__iexact=name,
        ).exclude(pk=department.pk)
        if duplicate.exists():
            raise ConflictError('A department with this name already exists.')
        department.name = name

    if 'manager' in data:
        department.manager = _clean_manager(data.get('manager'))

    if 'color' in data:
        department.color = _clean_color(data.get('color'))

    department.save()
    return department


def delete_department(user, department_pk):
    department = get_department(user, department_pk)
    department.delete()
