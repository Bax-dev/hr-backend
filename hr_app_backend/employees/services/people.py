import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Q

from hr_app_backend.departments.models import Department
from hr_app_backend.utils.errors import ConflictError, NotFoundError, ValidationError

from .employees import _clean_date, _clean_text, _require_company_account, get_employee, get_my_employee
from ..models import (
    Designation,
    Employee,
    EmployeeCustomField,
    EmployeeDocument,
    EmployeeEmergencyContact,
    EmployeeEmploymentHistory,
    Team,
)


def _clean_email(value, *, required=False):
    email = _clean_text(value).lower()
    if not email:
        if required:
            raise ValidationError('Email is required.')
        return ''
    try:
        validate_email(email)
    except DjangoValidationError as exc:
        raise ValidationError('A valid email address is required.') from exc
    return email


def _clean_bool(value):
    if isinstance(value, bool):
        return value
    if value in (None, ''):
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'yes', 'on'}:
            return True
        if normalized in {'false', '0', 'no', 'off'}:
            return False
    return bool(value)


def _get_department(organization, department_id):
    if department_id in (None, ''):
        return None
    try:
        return Department.objects.get(organization=organization, pk=department_id)
    except Department.DoesNotExist as exc:
        raise ValidationError('Selected department does not exist for this organization.') from exc


def _get_team(user, team_pk):
    organization = _require_company_account(user)
    try:
        return Team.objects.select_related('department').get(organization=organization, pk=team_pk)
    except Team.DoesNotExist as exc:
        raise NotFoundError('Team not found.') from exc


def _get_designation(user, designation_pk):
    organization = _require_company_account(user)
    try:
        return Designation.objects.get(organization=organization, pk=designation_pk)
    except Designation.DoesNotExist as exc:
        raise NotFoundError('Designation not found.') from exc


def _ensure_team_department(team, department):
    if team and department and team.department_id and team.department_id != department.id:
        raise ValidationError('Selected team does not belong to the selected department.')


def list_teams(user, *, search=None, department_id=None):
    organization = _require_company_account(user)
    queryset = Team.objects.filter(organization=organization).select_related('department').annotate(member_count=Count('members'))
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(lead__icontains=search)
            | Q(description__icontains=search)
            | Q(department__name__icontains=search)
        )
    if department_id:
        queryset = queryset.filter(department_id=department_id)
    return queryset.order_by('name')


@transaction.atomic
def create_team(user, data):
    organization = _require_company_account(user)
    name = _clean_text(data.get('name'))
    if len(name) < 2:
        raise ValidationError('Team name is required.')

    if Team.objects.filter(organization=organization, name__iexact=name).exists():
        raise ConflictError('A team with this name already exists.')

    department = _get_department(organization, data.get('department_id'))

    return Team.objects.create(
        organization=organization,
        name=name,
        department=department,
        lead=_clean_text(data.get('lead')),
        description=_clean_text(data.get('description')),
    )


@transaction.atomic
def update_team(user, team_pk, data):
    team = _get_team(user, team_pk)
    if 'name' in data:
        name = _clean_text(data.get('name'))
        if len(name) < 2:
            raise ValidationError('Team name is required.')
        duplicate = Team.objects.filter(organization=team.organization, name__iexact=name).exclude(pk=team.pk)
        if duplicate.exists():
            raise ConflictError('A team with this name already exists.')
        team.name = name

    if 'department_id' in data:
        team.department = _get_department(team.organization, data.get('department_id'))
    if 'lead' in data:
        team.lead = _clean_text(data.get('lead'))
    if 'description' in data:
        team.description = _clean_text(data.get('description'))

    team.save()
    return team


def delete_team(user, team_pk):
    team = _get_team(user, team_pk)
    team.delete()


def list_designations(user, *, search=None):
    organization = _require_company_account(user)
    queryset = Designation.objects.filter(organization=organization).annotate(employee_count=Count('employees'))
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | Q(level__icontains=search) | Q(description__icontains=search)
        )
    return queryset.order_by('title')


@transaction.atomic
def create_designation(user, data):
    organization = _require_company_account(user)
    title = _clean_text(data.get('title'))
    if len(title) < 2:
        raise ValidationError('Designation title is required.')

    if Designation.objects.filter(organization=organization, title__iexact=title).exists():
        raise ConflictError('A designation with this title already exists.')

    return Designation.objects.create(
        organization=organization,
        title=title,
        level=_clean_text(data.get('level')),
        description=_clean_text(data.get('description')),
    )


@transaction.atomic
def update_designation(user, designation_pk, data):
    designation = _get_designation(user, designation_pk)
    if 'title' in data:
        title = _clean_text(data.get('title'))
        if len(title) < 2:
            raise ValidationError('Designation title is required.')
        duplicate = Designation.objects.filter(organization=designation.organization, title__iexact=title).exclude(pk=designation.pk)
        if duplicate.exists():
            raise ConflictError('A designation with this title already exists.')
        designation.title = title

    if 'level' in data:
        designation.level = _clean_text(data.get('level'))
    if 'description' in data:
        designation.description = _clean_text(data.get('description'))

    designation.save()
    return designation


def delete_designation(user, designation_pk):
    designation = _get_designation(user, designation_pk)
    designation.delete()


def build_people_summary(user):
    organization = _require_company_account(user)
    return {
        'employees': Employee.objects.filter(organization=organization).count(),
        'active_employees': Employee.objects.filter(organization=organization, status=Employee.STATUS_ACTIVE).count(),
        'departments': Department.objects.filter(organization=organization).count(),
        'teams': Team.objects.filter(organization=organization).count(),
        'designations': Designation.objects.filter(organization=organization).count(),
    }


def build_organization_chart(user):
    organization = _require_company_account(user)
    employees = list(
        Employee.objects.filter(organization=organization)
        .select_related('manager_employee', 'team', 'designation', 'department_record')
        .order_by('first_name', 'last_name')
    )

    nodes = {}
    name_index = {}
    for employee in employees:
        full_name = f'{employee.first_name} {employee.last_name}'.strip()
        payload = {
            'id': str(employee.id),
            'employee_id': employee.employee_id,
            'name': full_name,
            'job_title': employee.position or (employee.designation.title if employee.designation else ''),
            'department': employee.department or (employee.department_record.name if employee.department_record else ''),
            'team': employee.team.name if employee.team else None,
            'status': employee.status,
            'manager_employee_id': str(employee.manager_employee_id) if employee.manager_employee_id else None,
            'manager_name': employee.manager or None,
            'children': [],
        }
        nodes[str(employee.id)] = payload
        name_index[full_name.strip().lower()] = str(employee.id)

    roots = []
    for employee in employees:
        node_id = str(employee.id)
        manager_id = str(employee.manager_employee_id) if employee.manager_employee_id else None
        if manager_id is None and employee.manager:
            manager_id = name_index.get(employee.manager.strip().lower())

        if manager_id and manager_id in nodes and manager_id != node_id:
            nodes[manager_id]['children'].append(nodes[node_id])
        else:
            roots.append(nodes[node_id])

    return roots


def _get_emergency_contact(employee, contact_pk):
    try:
        return employee.emergency_contacts.get(pk=contact_pk)
    except EmployeeEmergencyContact.DoesNotExist as exc:
        raise NotFoundError('Emergency contact not found.') from exc


def list_emergency_contacts(user, employee_pk):
    employee = get_employee(user, employee_pk)
    return employee.emergency_contacts.all()


@transaction.atomic
def create_emergency_contact(user, employee_pk, data):
    employee = get_employee(user, employee_pk)
    name = _clean_text(data.get('name'))
    relationship = _clean_text(data.get('relationship'))
    phone = _clean_text(data.get('phone'))
    if len(name) < 2:
        raise ValidationError('Contact name is required.')
    if len(relationship) < 2:
        raise ValidationError('Relationship is required.')
    if len(phone) < 5:
        raise ValidationError('Phone number is required.')

    is_primary = _clean_bool(data.get('is_primary'))
    if is_primary:
        employee.emergency_contacts.update(is_primary=False)

    return EmployeeEmergencyContact.objects.create(
        employee=employee,
        name=name,
        relationship=relationship,
        phone=phone,
        email=_clean_email(data.get('email')),
        address=_clean_text(data.get('address')),
        is_primary=is_primary,
    )


@transaction.atomic
def update_emergency_contact(user, employee_pk, contact_pk, data):
    employee = get_employee(user, employee_pk)
    contact = _get_emergency_contact(employee, contact_pk)

    if 'name' in data:
        name = _clean_text(data.get('name'))
        if len(name) < 2:
            raise ValidationError('Contact name is required.')
        contact.name = name
    if 'relationship' in data:
        relationship = _clean_text(data.get('relationship'))
        if len(relationship) < 2:
            raise ValidationError('Relationship is required.')
        contact.relationship = relationship
    if 'phone' in data:
        phone = _clean_text(data.get('phone'))
        if len(phone) < 5:
            raise ValidationError('Phone number is required.')
        contact.phone = phone
    if 'email' in data:
        contact.email = _clean_email(data.get('email'))
    if 'address' in data:
        contact.address = _clean_text(data.get('address'))
    if 'is_primary' in data:
        is_primary = _clean_bool(data.get('is_primary'))
        if is_primary:
            employee.emergency_contacts.exclude(pk=contact.pk).update(is_primary=False)
        contact.is_primary = is_primary

    contact.save()
    return contact


def delete_emergency_contact(user, employee_pk, contact_pk):
    employee = get_employee(user, employee_pk)
    _get_emergency_contact(employee, contact_pk).delete()


def _get_history_entry(employee, entry_pk):
    try:
        return employee.employment_history_entries.get(pk=entry_pk)
    except EmployeeEmploymentHistory.DoesNotExist as exc:
        raise NotFoundError('Employment history entry not found.') from exc


def list_employment_history(user, employee_pk):
    employee = get_employee(user, employee_pk)
    return employee.employment_history_entries.all()


@transaction.atomic
def create_employment_history(user, employee_pk, data):
    employee = get_employee(user, employee_pk)
    company_name = _clean_text(data.get('company_name'))
    job_title = _clean_text(data.get('job_title'))
    if len(company_name) < 2:
        raise ValidationError('Company name is required.')
    if len(job_title) < 2:
        raise ValidationError('Job title is required.')

    start_date = _clean_date(data.get('start_date'), 'Start date')
    if start_date is None:
        raise ValidationError('Start date is required.')
    end_date = _clean_date(data.get('end_date'), 'End date')
    if end_date and end_date < start_date:
        raise ValidationError('End date cannot be earlier than start date.')

    return EmployeeEmploymentHistory.objects.create(
        employee=employee,
        company_name=company_name,
        job_title=job_title,
        employment_type=_clean_text(data.get('employment_type')),
        start_date=start_date,
        end_date=end_date,
        responsibilities=_clean_text(data.get('responsibilities')),
    )


@transaction.atomic
def update_employment_history(user, employee_pk, entry_pk, data):
    employee = get_employee(user, employee_pk)
    entry = _get_history_entry(employee, entry_pk)

    if 'company_name' in data:
        company_name = _clean_text(data.get('company_name'))
        if len(company_name) < 2:
            raise ValidationError('Company name is required.')
        entry.company_name = company_name
    if 'job_title' in data:
        job_title = _clean_text(data.get('job_title'))
        if len(job_title) < 2:
            raise ValidationError('Job title is required.')
        entry.job_title = job_title
    if 'employment_type' in data:
        entry.employment_type = _clean_text(data.get('employment_type'))
    if 'responsibilities' in data:
        entry.responsibilities = _clean_text(data.get('responsibilities'))
    if 'start_date' in data:
        entry.start_date = _clean_date(data.get('start_date'), 'Start date')
        if entry.start_date is None:
            raise ValidationError('Start date is required.')
    if 'end_date' in data:
        entry.end_date = _clean_date(data.get('end_date'), 'End date')
    if entry.end_date and entry.start_date and entry.end_date < entry.start_date:
        raise ValidationError('End date cannot be earlier than start date.')

    entry.save()
    return entry


def delete_employment_history(user, employee_pk, entry_pk):
    employee = get_employee(user, employee_pk)
    _get_history_entry(employee, entry_pk).delete()


def _get_document(employee, document_pk):
    try:
        return employee.documents.get(pk=document_pk)
    except EmployeeDocument.DoesNotExist as exc:
        raise NotFoundError('Employee document not found.') from exc


def _get_document_employee(user, employee_pk):
    """Allow administrators, or a staff member accessing their own documents."""
    own_employee = get_my_employee(user)
    if own_employee is not None and str(own_employee.pk) == str(employee_pk):
        return own_employee
    return get_employee(user, employee_pk)


def list_employee_documents(user, employee_pk):
    employee = _get_document_employee(user, employee_pk)
    return employee.documents.all()


@transaction.atomic
def create_employee_document(user, employee_pk, data):
    employee = _get_document_employee(user, employee_pk)
    title = _clean_text(data.get('title'))
    document_type = _clean_text(data.get('document_type'))
    if len(title) < 2:
        raise ValidationError('Document title is required.')
    if len(document_type) < 2:
        raise ValidationError('Document type is required.')

    issued_date = _clean_date(data.get('issued_date'), 'Issued date')
    expiry_date = _clean_date(data.get('expiry_date'), 'Expiry date')
    if issued_date and expiry_date and expiry_date < issued_date:
        raise ValidationError('Expiry date cannot be earlier than issued date.')

    return EmployeeDocument.objects.create(
        employee=employee,
        title=title,
        document_type=document_type,
        file_name=_clean_text(data.get('file_name')),
        file_url=_clean_text(data.get('file_url')),
        issued_date=issued_date,
        expiry_date=expiry_date,
        notes=_clean_text(data.get('notes')),
    )


@transaction.atomic
def update_employee_document(user, employee_pk, document_pk, data):
    employee = _get_document_employee(user, employee_pk)
    document = _get_document(employee, document_pk)

    if 'title' in data:
        title = _clean_text(data.get('title'))
        if len(title) < 2:
            raise ValidationError('Document title is required.')
        document.title = title
    if 'document_type' in data:
        document_type = _clean_text(data.get('document_type'))
        if len(document_type) < 2:
            raise ValidationError('Document type is required.')
        document.document_type = document_type
    if 'file_name' in data:
        document.file_name = _clean_text(data.get('file_name'))
    if 'file_url' in data:
        document.file_url = _clean_text(data.get('file_url'))
    if 'notes' in data:
        document.notes = _clean_text(data.get('notes'))
    if 'issued_date' in data:
        document.issued_date = _clean_date(data.get('issued_date'), 'Issued date')
    if 'expiry_date' in data:
        document.expiry_date = _clean_date(data.get('expiry_date'), 'Expiry date')
    if document.issued_date and document.expiry_date and document.expiry_date < document.issued_date:
        raise ValidationError('Expiry date cannot be earlier than issued date.')

    document.save()
    return document


def delete_employee_document(user, employee_pk, document_pk):
    employee = _get_document_employee(user, employee_pk)
    _get_document(employee, document_pk).delete()


def _get_custom_field(employee, field_pk):
    try:
        return employee.custom_fields.get(pk=field_pk)
    except EmployeeCustomField.DoesNotExist as exc:
        raise NotFoundError('Custom field not found.') from exc


def _clean_field_type(value):
    field_type = _clean_text(value) or EmployeeCustomField.TYPE_TEXT
    valid = {choice for choice, _ in EmployeeCustomField.FIELD_TYPES}
    if field_type not in valid:
        raise ValidationError(f'Field type must be one of: {", ".join(sorted(valid))}.')
    return field_type


def list_custom_fields(user, employee_pk):
    employee = get_employee(user, employee_pk)
    return employee.custom_fields.all()


@transaction.atomic
def create_custom_field(user, employee_pk, data):
    employee = get_employee(user, employee_pk)
    field_name = _clean_text(data.get('field_name'))
    if len(field_name) < 2:
        raise ValidationError('Field name is required.')
    if EmployeeCustomField.objects.filter(employee=employee, field_name__iexact=field_name).exists():
        raise ConflictError('A custom field with this name already exists for the employee.')

    return EmployeeCustomField.objects.create(
        employee=employee,
        field_name=field_name,
        field_type=_clean_field_type(data.get('field_type')),
        value='' if data.get('value') is None else str(data.get('value')),
    )


@transaction.atomic
def update_custom_field(user, employee_pk, field_pk, data):
    employee = get_employee(user, employee_pk)
    field = _get_custom_field(employee, field_pk)

    if 'field_name' in data:
        field_name = _clean_text(data.get('field_name'))
        if len(field_name) < 2:
            raise ValidationError('Field name is required.')
        duplicate = EmployeeCustomField.objects.filter(employee=employee, field_name__iexact=field_name).exclude(pk=field.pk)
        if duplicate.exists():
            raise ConflictError('A custom field with this name already exists for the employee.')
        field.field_name = field_name

    if 'field_type' in data:
        field.field_type = _clean_field_type(data.get('field_type'))
    if 'value' in data:
        field.value = '' if data.get('value') is None else str(data.get('value'))

    field.save()
    return field


def delete_custom_field(user, employee_pk, field_pk):
    employee = get_employee(user, employee_pk)
    _get_custom_field(employee, field_pk).delete()
