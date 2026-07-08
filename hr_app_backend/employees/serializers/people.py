def _value(payload, *keys, default=''):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


TEAM_FIELDS = [
    ('name', 'name'),
    ('department_id', 'department_id', 'departmentId'),
    ('lead', 'lead'),
    ('description', 'description'),
]

DESIGNATION_FIELDS = [
    ('title', 'title'),
    ('level', 'level'),
    ('description', 'description'),
]

EMERGENCY_CONTACT_FIELDS = [
    ('name', 'name'),
    ('relationship', 'relationship'),
    ('phone', 'phone'),
    ('email', 'email'),
    ('address', 'address'),
    ('is_primary', 'is_primary', 'isPrimary'),
]

EMPLOYMENT_HISTORY_FIELDS = [
    ('company_name', 'company_name', 'companyName'),
    ('job_title', 'job_title', 'jobTitle'),
    ('employment_type', 'employment_type', 'employmentType'),
    ('start_date', 'start_date', 'startDate'),
    ('end_date', 'end_date', 'endDate'),
    ('responsibilities', 'responsibilities'),
]

DOCUMENT_FIELDS = [
    ('title', 'title'),
    ('document_type', 'document_type', 'documentType'),
    ('file_name', 'file_name', 'fileName'),
    ('file_url', 'file_url', 'fileUrl'),
    ('issued_date', 'issued_date', 'issuedDate'),
    ('expiry_date', 'expiry_date', 'expiryDate'),
    ('notes', 'notes'),
]

CUSTOM_FIELD_FIELDS = [
    ('field_name', 'field_name', 'fieldName'),
    ('field_type', 'field_type', 'fieldType'),
    ('value', 'value'),
]


def _payload(payload, field_map, partial=False):
    data = {}
    for field, *keys in field_map:
        if partial and not any(key in payload for key in keys):
            continue
        data[field] = _value(payload, *keys, default=None if partial else '')
    return data


def team_payload(payload, partial=False):
    return _payload(payload, TEAM_FIELDS, partial=partial)


def designation_payload(payload, partial=False):
    return _payload(payload, DESIGNATION_FIELDS, partial=partial)


def emergency_contact_payload(payload, partial=False):
    return _payload(payload, EMERGENCY_CONTACT_FIELDS, partial=partial)


def employment_history_payload(payload, partial=False):
    return _payload(payload, EMPLOYMENT_HISTORY_FIELDS, partial=partial)


def employee_document_payload(payload, partial=False):
    return _payload(payload, DOCUMENT_FIELDS, partial=partial)


def custom_field_payload(payload, partial=False):
    return _payload(payload, CUSTOM_FIELD_FIELDS, partial=partial)


def serialize_team(team, member_count=0):
    return {
        'id': team.id,
        'name': team.name,
        'department_id': team.department_id,
        'department_name': team.department.name if team.department else None,
        'lead': team.lead or None,
        'description': team.description or None,
        'member_count': member_count,
    }


def serialize_designation(designation, employee_count=0):
    return {
        'id': designation.id,
        'title': designation.title,
        'level': designation.level or None,
        'description': designation.description or None,
        'employee_count': employee_count,
    }


def serialize_emergency_contact(contact):
    return {
        'id': contact.id,
        'name': contact.name,
        'relationship': contact.relationship,
        'phone': contact.phone,
        'email': contact.email or None,
        'address': contact.address or None,
        'is_primary': contact.is_primary,
    }


def serialize_employment_history(entry):
    return {
        'id': entry.id,
        'company_name': entry.company_name,
        'job_title': entry.job_title,
        'employment_type': entry.employment_type or None,
        'start_date': entry.start_date.isoformat(),
        'end_date': entry.end_date.isoformat() if entry.end_date else None,
        'responsibilities': entry.responsibilities or None,
    }


def serialize_employee_document(document):
    return {
        'id': document.id,
        'title': document.title,
        'document_type': document.document_type,
        'file_name': document.file_name or None,
        'file_url': document.file_url or None,
        'issued_date': document.issued_date.isoformat() if document.issued_date else None,
        'expiry_date': document.expiry_date.isoformat() if document.expiry_date else None,
        'notes': document.notes or None,
    }


def serialize_custom_field(field):
    return {
        'id': field.id,
        'field_name': field.field_name,
        'field_type': field.field_type,
        'value': field.value,
    }
