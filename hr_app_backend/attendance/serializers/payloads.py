PUNCH_FIELDS = ('latitude', 'longitude', 'accuracy')


def punch_payload(payload):
    return {field: payload.get(field) for field in PUNCH_FIELDS}


def remote_mark_payload(payload):
    employee_ids = payload.get('employee_ids')
    if employee_ids is None:
        employee_ids = payload.get('employeeIds')
    employee_id = payload.get('employee_id')
    if employee_id is None:
        employee_id = payload.get('employeeId')
    return {
        'date': payload.get('date'),
        'employee_ids': employee_ids,
        'employee_id': employee_id,
    }


def remote_workers_payload(payload):
    employee_ids = payload.get('employee_ids')
    if employee_ids is None:
        employee_ids = payload.get('employeeIds')
    return {
        'employee_ids': employee_ids,
    }


# Accepts both snake_case (radius_meters) and camelCase (radiusMeters) keys.
LOCATION_FIELDS = [
    ('name', ('name',)),
    ('address', ('address',)),
    ('latitude', ('latitude',)),
    ('longitude', ('longitude',)),
    ('radius_meters', ('radius_meters', 'radiusMeters')),
]


def office_location_payload(payload, partial=False):
    data = {}
    for field, keys in LOCATION_FIELDS:
        present = next((key for key in keys if key in payload), None)
        if present is None:
            if partial:
                continue
            data[field] = None
        else:
            data[field] = payload.get(present)
    return data
