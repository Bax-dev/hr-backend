def _value(payload, *keys, default=''):
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


DEPARTMENT_FIELDS = [
    ('name', 'name'),
    ('manager', 'manager'),
    ('color', 'color'),
]


def department_payload(payload, partial=False):
    data = {}
    for field, *keys in DEPARTMENT_FIELDS:
        if partial and not any(key in payload for key in keys):
            continue
        data[field] = _value(payload, *keys, default=None if partial else '')
    return data
