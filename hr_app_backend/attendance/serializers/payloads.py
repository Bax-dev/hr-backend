PUNCH_FIELDS = ('latitude', 'longitude', 'accuracy')


def punch_payload(payload):
    return {field: payload.get(field) for field in PUNCH_FIELDS}
