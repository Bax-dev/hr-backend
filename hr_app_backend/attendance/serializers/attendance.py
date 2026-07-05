import datetime


def _hours_worked(record):
    if record.check_out is None:
        return None
    start = datetime.datetime.combine(record.date, record.check_in)
    end = datetime.datetime.combine(record.date, record.check_out)
    if end < start:
        return 0.0
    return round((end - start).total_seconds() / 3600, 1)


def serialize_attendance_record(record):
    employee = record.employee
    return {
        'id': record.id,
        'employee_id': employee.id,
        'employee_name': f'{employee.first_name} {employee.last_name}'.strip(),
        'date': record.date.isoformat(),
        'check_in': record.check_in.strftime('%H:%M'),
        'check_out': record.check_out.strftime('%H:%M') if record.check_out else None,
        'status': record.get_status_display(),
        'hours_worked': _hours_worked(record),
        'location_name': record.location.name if record.location else None,
    }


def serialize_office_location(location):
    return {
        'id': location.id,
        'name': location.name,
        'address': location.address,
        'latitude': float(location.latitude),
        'longitude': float(location.longitude),
        'radius_meters': location.radius_meters,
    }
