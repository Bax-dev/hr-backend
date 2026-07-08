def _value(payload, *keys, default=''):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


def _payload(payload, field_map, partial=False):
    data = {}
    for field, *keys in field_map:
        if partial and not any(key in payload for key in keys):
            continue
        data[field] = _value(payload, *keys, default=None if partial else '')
    return data


JOB_FIELDS = [
    ('title', 'title'),
    ('department', 'department'),
    ('location', 'location'),
    ('type', 'type'),
    ('status', 'status'),
    ('description', 'description'),
]

ONBOARDING_FIELDS = [
    ('employee_name', 'employee_name', 'employeeName'),
    ('start_date', 'start_date', 'startDate'),
    ('owner', 'owner'),
    ('status', 'status'),
    ('equipment_ready', 'equipment_ready', 'equipmentReady'),
    ('notes', 'notes'),
]

PERFORMANCE_FIELDS = [
    ('employee_name', 'employee_name', 'employeeName'),
    ('review_cycle', 'review_cycle', 'reviewCycle'),
    ('owner', 'owner'),
    ('priority', 'priority'),
    ('status', 'status'),
    ('notes', 'notes'),
]

LEARNING_FIELDS = [
    ('program_name', 'program_name', 'programName'),
    ('audience', 'audience'),
    ('owner', 'owner'),
    ('status', 'status'),
    ('priority', 'priority'),
    ('notes', 'notes'),
]

OFFBOARDING_FIELDS = [
    ('employee_name', 'employee_name', 'employeeName'),
    ('last_working_day', 'last_working_day', 'lastWorkingDay'),
    ('owner', 'owner'),
    ('status', 'status'),
    ('assets_cleared', 'assets_cleared', 'assetsCleared'),
    ('notes', 'notes'),
]


def job_payload(payload, partial=False):
    return _payload(payload, JOB_FIELDS, partial=partial)


def onboarding_payload(payload, partial=False):
    return _payload(payload, ONBOARDING_FIELDS, partial=partial)


def performance_payload(payload, partial=False):
    return _payload(payload, PERFORMANCE_FIELDS, partial=partial)


def learning_payload(payload, partial=False):
    return _payload(payload, LEARNING_FIELDS, partial=partial)


def offboarding_payload(payload, partial=False):
    return _payload(payload, OFFBOARDING_FIELDS, partial=partial)
