import datetime
import decimal
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q

from hr_app_backend.authentication.models import UserProfile
from hr_app_backend.authentication.services.employee_invites import create_employee_invite_token
from hr_app_backend.services import render_email_template
from hr_app_backend.third_parties import get_email_service
from hr_app_backend.utils import get_env
from hr_app_backend.departments.models import Department
from hr_app_backend.utils.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

from ..models import Designation, Employee, Team

User = get_user_model()
REQUIRED_FIELDS = ('first_name', 'last_name', 'email')
DEFAULT_LOGIN_URL = 'http://localhost:5173/login'


def _require_organization(user):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is None:
        raise PermissionDeniedError('A company account is required to manage employees.')
    return organization


def _require_company_account(user):
    """Require a company (admin) account for managing the employee directory.

    Individual/staff accounts are self-service only: they may view and edit
    their own record via the ``/me`` endpoints, but cannot list or access other
    employees.
    """
    organization = _require_organization(user)
    profile = getattr(user, 'profile', None)
    if getattr(profile, 'account_type', None) != UserProfile.ACCOUNT_TYPE_COMPANY:
        raise PermissionDeniedError('Only company administrators can manage employees.')
    return organization


def _validate_email_address(email):
    try:
        validate_email(email)
    except DjangoValidationError as exc:
        raise ValidationError('A valid email address is required.') from exc


def _clean_date(value, label):
    if value in (None, ''):
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError(f'{label} must be an ISO date (YYYY-MM-DD).') from exc


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


def _clean_text(value):
    return (value or '').strip()


def _clean_bool(value):
    if isinstance(value, bool):
        return value
    if value in (None, ''):
        return False
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _display_employee_name(employee):
    if employee is None:
        return ''
    return f'{employee.first_name} {employee.last_name}'.strip()


def _build_invite_url(token):
    base_url = get_env('FRONTEND_LOGIN_URL', DEFAULT_LOGIN_URL).strip() or DEFAULT_LOGIN_URL
    base_url = base_url.rsplit('/login', 1)[0] + '/accept-invite'
    separator = '&' if '?' in base_url else '?'
    return f'{base_url}{separator}{urlencode({"token": token})}'


def _send_employee_invite_email(*, employee, user):
    invite_url = _build_invite_url(create_employee_invite_token(user))
    html_body = render_email_template(
        'emails/employee_invite.html',
        {
            'email_title': 'Your Workiva employee account is ready',
            'email_eyebrow': 'Employee Access',
            'email_heading': 'Your employee account is ready',
            'email_intro': 'Use the secure link below to finish setting up your employee account.',
            'recipient_email': employee.email,
            'invite_url': invite_url,
        },
    )
    text_body = (
        f'Your Workiva employee account is ready.\n\n'
        f'Email: {employee.email}\n'
        f'Complete account setup: {invite_url}\n\n'
        f'This secure invitation link expires in 7 days.'
    )
    get_email_service().send_mail(
        subject='Your Workiva employee account is ready',
        body=text_body,
        html_body=html_body,
        to_emails=[employee.email],
    )


def _create_employee_user_account(*, employee):
    if User.objects.filter(email=employee.email).exists():
        raise ConflictError('A user account with this employee email already exists.')

    user = User.objects.create_user(
        username=employee.email,
        email=employee.email,
        first_name=employee.first_name,
        last_name=employee.last_name,
    )
    UserProfile.objects.create(
        user=user,
        account_type=UserProfile.ACCOUNT_TYPE_INDIVIDUAL,
        full_name=_display_employee_name(employee),
        phone=employee.phone,
        organization=employee.organization,
        employee=employee,
        must_change_password=False,
    )
    user.set_unusable_password()
    user.save(update_fields=['password'])
    _send_employee_invite_email(employee=employee, user=user)
    return user


def _next_employee_id(organization):
    count = Employee.objects.filter(organization=organization).count()
    while True:
        count += 1
        candidate = f'EMP-{count:04d}'
        if not Employee.objects.filter(organization=organization, employee_id=candidate).exists():
            return candidate


def _resolve_department(organization, department_id):
    if department_id in (None, ''):
        return None
    try:
        return Department.objects.get(organization=organization, pk=department_id)
    except Department.DoesNotExist as exc:
        raise ValidationError('Selected department does not exist for this organization.') from exc


def _resolve_team(organization, team_id):
    if team_id in (None, ''):
        return None
    try:
        return Team.objects.select_related('department').get(organization=organization, pk=team_id)
    except Team.DoesNotExist as exc:
        raise ValidationError('Selected team does not exist for this organization.') from exc


def _resolve_designation(organization, designation_id):
    if designation_id in (None, ''):
        return None
    try:
        return Designation.objects.get(organization=organization, pk=designation_id)
    except Designation.DoesNotExist as exc:
        raise ValidationError('Selected designation does not exist for this organization.') from exc


def _resolve_manager(organization, manager_employee_id, current_employee=None):
    if manager_employee_id in (None, ''):
        return None
    try:
        manager = Employee.objects.get(organization=organization, pk=manager_employee_id)
    except Employee.DoesNotExist as exc:
        raise ValidationError('Selected manager does not exist for this organization.') from exc

    if current_employee is not None and manager.pk == current_employee.pk:
        raise ValidationError('An employee cannot be their own manager.')

    return manager


def _validate_relationships(department_record, team):
    if department_record and team and team.department_id and team.department_id != department_record.id:
        raise ValidationError('Selected team does not belong to the selected department.')


def list_employees(user, search=None, department=None, status=None):
    organization = _require_company_account(user)
    queryset = Employee.objects.filter(organization=organization).select_related(
        'department_record',
        'team',
        'designation',
        'manager_employee',
        'user_profile',
    )

    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(employee_id__icontains=search)
        )
    if department:
        queryset = queryset.filter(
            Q(department__iexact=department)
            | Q(department_record__name__iexact=department)
        )
    if status:
        queryset = queryset.filter(status=_clean_status(status))

    return queryset


def get_employee(user, employee_pk):
    organization = _require_company_account(user)
    try:
        return Employee.objects.select_related(
            'department_record',
            'team',
            'designation',
            'manager_employee',
            'user_profile',
        ).get(organization=organization, pk=employee_pk)
    except Employee.DoesNotExist as exc:
        raise NotFoundError('Employee not found.') from exc


# Fields a staff member may edit on their own profile from the portal.
SELF_EDITABLE_FIELDS = ('first_name', 'last_name', 'email', 'phone', 'gender', 'country', 'date_of_birth')
# Number of self-service profile edits allowed per calendar month.
SELF_EDIT_MONTHLY_LIMIT = 3


def _current_period():
    return datetime.date.today().strftime('%Y-%m')


def _edits_used_this_month(employee):
    if employee is None:
        return 0
    return employee.self_edits_used if employee.self_edits_period == _current_period() else 0


def my_employee_profile(employee):
    """Shape the self-service profile response, including the edit quota."""
    used = _edits_used_this_month(employee)
    # No linked employee means there is nothing to edit, so report no quota.
    remaining = max(SELF_EDIT_MONTHLY_LIMIT - used, 0) if employee is not None else 0
    return {
        'employee': employee,
        'edits_used_this_month': used,
        'edits_remaining_this_month': remaining,
    }


def get_my_employee(user):
    """Return the employee record linked to the signed-in user, if any.

    Staff accounts are provisioned with a UserProfile pointing at their
    Employee record. Self-signed-up individuals (and company owners) have no
    linked employee, so this returns ``None`` rather than raising.
    """
    profile = getattr(user, 'profile', None)
    employee = getattr(profile, 'employee', None) if profile else None
    if employee is None:
        return None

    return Employee.objects.select_related(
        'department_record',
        'team',
        'designation',
        'manager_employee',
        'user_profile',
    ).get(pk=employee.pk)


SELF_EDIT_QUOTA_FIELDS = frozenset({'email', 'first_name', 'last_name', 'phone', 'gender', 'country', 'date_of_birth'})


@transaction.atomic
def update_my_employee(user, data):
    """Apply a staff member's own edits to their linked employee record.

    Personal fields are capped at a few edits per month; the profile photo is
    exempt from that quota since it isn't a "personal detail" edit.
    """
    employee = get_my_employee(user)
    if employee is None:
        raise NotFoundError('No employee profile is linked to this account.')

    period = _current_period()
    used = employee.self_edits_used if employee.self_edits_period == period else 0
    if SELF_EDIT_QUOTA_FIELDS.intersection(data) and used >= SELF_EDIT_MONTHLY_LIMIT:
        raise PermissionDeniedError(
            f'You have reached your monthly profile edit limit of {SELF_EDIT_MONTHLY_LIMIT}.'
        )

    changed = False
    avatar_changed = False

    if 'avatar' in data:
        avatar = _clean_text(data['avatar'])
        if avatar != employee.avatar:
            employee.avatar = avatar
            avatar_changed = True

    if 'email' in data and data['email'] is not None:
        email = _clean_text(data['email']).lower()
        _validate_email_address(email)
        duplicate = Employee.objects.filter(
            organization=employee.organization, email=email
        ).exclude(pk=employee.pk)
        if duplicate.exists():
            raise ConflictError('An employee with this email already exists.')
        if email != employee.email:
            employee.email = email
            changed = True

    for field in ('first_name', 'last_name'):
        if field in data and data[field] is not None:
            value = _clean_text(data[field])
            if not value:
                raise ValidationError(f'{field.replace("_", " ").capitalize()} cannot be empty.')
            if value != getattr(employee, field):
                setattr(employee, field, value)
                changed = True

    for field in ('phone', 'gender', 'country'):
        if field in data and data[field] is not None:
            value = _clean_text(data[field])
            if value != getattr(employee, field):
                setattr(employee, field, value)
                changed = True

    if 'date_of_birth' in data:
        dob = _clean_date(data['date_of_birth'], 'Date of birth')
        if dob != employee.date_of_birth:
            employee.date_of_birth = dob
            changed = True

    if changed:
        employee.self_edits_used = used + 1
        employee.self_edits_period = period

    if changed or avatar_changed:
        employee.save()

    return employee


@transaction.atomic
def create_employee(user, data):
    organization = _require_company_account(user)

    for field in REQUIRED_FIELDS:
        if not _clean_text(data.get(field)):
            raise ValidationError(f'{field.replace("_", " ").capitalize()} is required.')

    email = _clean_text(data['email']).lower()
    _validate_email_address(email)

    if Employee.objects.filter(organization=organization, email=email).exists():
        raise ConflictError('An employee with this email already exists.')
    if _clean_bool(data.get('send_invite')) and User.objects.filter(email=email).exists():
        raise ConflictError('A user account with this employee email already exists.')

    employee_id = _clean_text(data.get('employee_id')) or _next_employee_id(organization)
    if Employee.objects.filter(organization=organization, employee_id=employee_id).exists():
        raise ConflictError('An employee with this employee ID already exists.')

    department_record = _resolve_department(organization, data.get('department_record_id'))
    team = _resolve_team(organization, data.get('team_id'))
    designation = _resolve_designation(organization, data.get('designation_id'))
    manager_employee = _resolve_manager(organization, data.get('manager_employee_id'))
    _validate_relationships(department_record, team)

    department_name = _clean_text(data.get('department')) or (department_record.name if department_record else '')
    position = _clean_text(data.get('position')) or (designation.title if designation else '')
    manager_name = _clean_text(data.get('manager')) or _display_employee_name(manager_employee)

    employee = Employee.objects.create(
        organization=organization,
        employee_id=employee_id,
        first_name=_clean_text(data['first_name']),
        last_name=_clean_text(data['last_name']),
        email=email,
        phone=_clean_text(data.get('phone')),
        department=department_name,
        department_record=department_record,
        team=team,
        position=position,
        designation=designation,
        status=_clean_status(data.get('status')),
        gender=_clean_text(data.get('gender')),
        country=_clean_text(data.get('country')),
        hire_date=_clean_date(data.get('hire_date'), 'Hire date'),
        date_of_birth=_clean_date(data.get('date_of_birth'), 'Date of birth'),
        salary=_clean_salary(data.get('salary')),
        avatar=_clean_text(data.get('avatar')),
        manager=manager_name,
        manager_employee=manager_employee,
    )
    if _clean_bool(data.get('send_invite')):
        _create_employee_user_account(employee=employee)
    return employee


@transaction.atomic
def update_employee(user, employee_pk, data):
    employee = get_employee(user, employee_pk)

    if 'email' in data:
        email = _clean_text(data['email']).lower()
        _validate_email_address(email)
        duplicate = Employee.objects.filter(
            organization=employee.organization, email=email
        ).exclude(pk=employee.pk)
        if duplicate.exists():
            raise ConflictError('An employee with this email already exists.')
        employee.email = email

    if 'employee_id' in data:
        employee_id = _clean_text(data['employee_id'])
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
            value = _clean_text(data[field])
            if not value:
                raise ValidationError(f'{field.replace("_", " ").capitalize()} cannot be empty.')
            setattr(employee, field, value)

    for field in ('phone', 'gender', 'country', 'avatar'):
        if field in data:
            setattr(employee, field, _clean_text(data[field]))

    if 'department_record_id' in data:
        employee.department_record = _resolve_department(employee.organization, data.get('department_record_id'))
    if 'team_id' in data:
        employee.team = _resolve_team(employee.organization, data.get('team_id'))
    if 'designation_id' in data:
        employee.designation = _resolve_designation(employee.organization, data.get('designation_id'))
    if 'manager_employee_id' in data:
        employee.manager_employee = _resolve_manager(employee.organization, data.get('manager_employee_id'), current_employee=employee)

    _validate_relationships(employee.department_record, employee.team)

    if 'department' in data:
        employee.department = _clean_text(data['department'])
    elif 'department_record_id' in data:
        employee.department = employee.department_record.name if employee.department_record else ''

    if 'position' in data:
        employee.position = _clean_text(data['position'])
    elif 'designation_id' in data:
        employee.position = employee.designation.title if employee.designation else ''

    if 'manager' in data:
        employee.manager = _clean_text(data['manager'])
    elif 'manager_employee_id' in data:
        employee.manager = _display_employee_name(employee.manager_employee)

    if 'status' in data:
        employee.status = _clean_status(data['status'])
    if 'hire_date' in data:
        employee.hire_date = _clean_date(data['hire_date'], 'Hire date')
    if 'date_of_birth' in data:
        employee.date_of_birth = _clean_date(data['date_of_birth'], 'Date of birth')
    if 'salary' in data:
        employee.salary = _clean_salary(data['salary'])

    employee.save()
    return employee


def delete_employee(user, employee_pk):
    employee = get_employee(user, employee_pk)
    employee.delete()
