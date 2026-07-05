import datetime

from django.db import transaction

from hr_app_backend.employees.models import Employee
from hr_app_backend.utils import local_now, today_local
from hr_app_backend.utils.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

from ..models import AttendanceRecord, OfficeLocation
from .geo import format_distance_meters, haversine_distance_meters

# Check-ins after this local time are marked Late.
LATE_CUTOFF = datetime.time(hour=9, minute=15)


def _require_organization(user):
    profile = getattr(user, 'profile', None)
    organization = getattr(profile, 'organization', None) if profile else None
    if organization is None:
        raise PermissionDeniedError('A company account is required to manage attendance.')
    return organization


def _clean_status(value):
    status = str(value).strip().lower().replace(' ', '_').replace('-', '_')
    valid = {choice for choice, _ in AttendanceRecord.STATUSES}
    if status not in valid:
        raise ValidationError(f'Status must be one of: {", ".join(sorted(valid))}.')
    return status


def _clean_date(value):
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError('Date must be an ISO date (YYYY-MM-DD).') from exc


def _resolve_employee(user, organization):
    employee = (
        Employee.objects.filter(organization=organization, email__iexact=user.email)
        .exclude(status=Employee.STATUS_TERMINATED)
        .first()
    )
    if employee is None:
        raise NotFoundError('Your user account is not linked to an employee record.')
    return employee


def _clean_coordinates(data):
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    try:
        return float(latitude), float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValidationError('Your location is required to sign attendance.') from exc


def _resolve_geofence(organization, latitude, longitude):
    nearest = None
    nearest_distance = None
    for location in OfficeLocation.objects.filter(organization=organization, is_active=True):
        distance = haversine_distance_meters(latitude, longitude, location.latitude, location.longitude)
        if nearest_distance is None or distance < nearest_distance:
            nearest, nearest_distance = location, distance

    if nearest is None:
        raise PermissionDeniedError(
            'Attendance can only be signed at an office location. No office locations are configured.'
        )
    if nearest_distance > nearest.radius_meters:
        raise PermissionDeniedError(
            'Attendance can only be signed at an office location. '
            f'You are {format_distance_meters(nearest_distance)} from {nearest.name}; '
            f'you must be within {nearest.radius_meters} m of an office location.'
        )
    return nearest


def list_attendance(user, date=None, status=None, employee_id=None):
    organization = _require_organization(user)
    queryset = AttendanceRecord.objects.select_related('employee', 'location').filter(
        organization=organization
    )

    if date:
        queryset = queryset.filter(date=_clean_date(date))
    if status:
        queryset = queryset.filter(status=_clean_status(status))
    if employee_id:
        queryset = queryset.filter(employee_id=employee_id)

    return queryset


def list_locations(user):
    organization = _require_organization(user)
    return OfficeLocation.objects.filter(organization=organization, is_active=True)


@transaction.atomic
def check_in(user, data):
    organization = _require_organization(user)
    latitude, longitude = _clean_coordinates(data)
    location = _resolve_geofence(organization, latitude, longitude)
    employee = _resolve_employee(user, organization)

    now = local_now()
    if AttendanceRecord.objects.filter(employee=employee, date=now.date()).exists():
        raise ConflictError('You have already checked in today.')

    status = (
        AttendanceRecord.STATUS_LATE
        if now.time() > LATE_CUTOFF
        else AttendanceRecord.STATUS_PRESENT
    )
    return AttendanceRecord.objects.create(
        organization=organization,
        employee=employee,
        date=now.date(),
        check_in=now.time().replace(second=0, microsecond=0),
        status=status,
        location=location,
        check_in_latitude=latitude,
        check_in_longitude=longitude,
    )


@transaction.atomic
def check_out(user, data):
    organization = _require_organization(user)
    latitude, longitude = _clean_coordinates(data)
    _resolve_geofence(organization, latitude, longitude)
    employee = _resolve_employee(user, organization)

    record = AttendanceRecord.objects.filter(employee=employee, date=today_local()).first()
    if record is None:
        raise NotFoundError('You have not checked in today.')
    if record.check_out is not None:
        raise ConflictError('You have already checked out today.')

    record.check_out = local_now().time().replace(second=0, microsecond=0)
    record.check_out_latitude = latitude
    record.check_out_longitude = longitude
    record.save()
    return record
