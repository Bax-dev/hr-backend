def _value(payload, *keys, default=''):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


LEAVE_FIELDS = [
    ('employee_id', 'employee_id', 'employeeId'),
    ('leave_type', 'leave_type', 'leaveType'),
    ('start_date', 'start_date', 'startDate'),
    ('end_date', 'end_date', 'endDate'),
    ('reason', 'reason'),
    ('rejection_reason', 'rejection_reason', 'rejectionReason'),
    ('status', 'status'),
]


def leave_payload(payload, partial=False):
    data = {}
    for field, *keys in LEAVE_FIELDS:
        if partial and not any(key in payload for key in keys):
            continue
        data[field] = _value(payload, *keys, default=None if partial else '')
    return data
