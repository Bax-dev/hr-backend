def _value(payload, *keys, default=''):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


EMPLOYEE_FIELDS = [
    ('employee_id', 'employee_id', 'employeeId'),
    ('first_name', 'first_name', 'firstName'),
    ('last_name', 'last_name', 'lastName'),
    ('email', 'email'),
    ('phone', 'phone'),
    ('department', 'department'),
    ('department_record_id', 'department_record_id', 'departmentRecordId', 'departmentId'),
    ('team_id', 'team_id', 'teamId'),
    ('position', 'position'),
    ('designation_id', 'designation_id', 'designationId'),
    ('status', 'status'),
    ('gender', 'gender'),
    ('country', 'country'),
    ('hire_date', 'hire_date', 'hireDate'),
    ('date_of_birth', 'date_of_birth', 'dateOfBirth'),
    ('salary', 'salary'),
    ('avatar', 'avatar'),
    ('manager', 'manager'),
    ('manager_employee_id', 'manager_employee_id', 'managerEmployeeId', 'managerId'),
]


def employee_payload(payload, partial=False):
    """Normalize a request body to model field names.

    With partial=True (updates) only the keys present in the body are
    returned, so absent fields are left untouched.
    """
    data = {}
    for field, *keys in EMPLOYEE_FIELDS:
        if partial and not any(key in payload for key in keys):
            continue
        data[field] = _value(payload, *keys, default=None if partial else '')
    return data
