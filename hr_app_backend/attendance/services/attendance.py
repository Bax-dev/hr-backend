import datetime

from django.db import transaction

from hr_app_backend.employees.models import Employee
from hr_app_backend.authentication.models import UserProfile
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


def _require_company_account(user):
    organization = _require_organization(user)
    profile = getattr(user, 'profile', None)
    if getattr(profile, 'account_type', None) != UserProfile.ACCOUNT_TYPE_COMPANY:
        raise PermissionDeniedError('Only company administrators can manage attendance locations.')
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
    profile = getattr(user, 'profile', None)
    linked_employee = getattr(profile, 'employee', None) if profile else None
    if linked_employee is not None and linked_employee.organization_id == organization.id:
        if linked_employee.status == Employee.STATUS_TERMINATED:
            raise NotFoundError('Your linked employee record is no longer active.')
        return linked_employee
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

    # Staff accounts may only view their own attendance. Their auth user ID and
    # employee ID are different values, so resolve the linked employee by email.
    profile = getattr(user, 'profile', None)
    if getattr(profile, 'account_type', None) == 'individual':
        queryset = queryset.filter(employee=_resolve_employee(user, organization))

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


def get_location(user, location_id):
    organization = _require_organization(user)
    location = OfficeLocation.objects.filter(organization=organization, id=location_id).first()
    if location is None:
        raise NotFoundError('Location not found.')
    return location


def _clean_latitude(value):
    try:
        latitude = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError('Latitude must be a number.') from exc
    if not -90 <= latitude <= 90:
        raise ValidationError('Latitude must be between -90 and 90.')
    return latitude


def _clean_longitude(value):
    try:
        longitude = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError('Longitude must be a number.') from exc
    if not -180 <= longitude <= 180:
        raise ValidationError('Longitude must be between -180 and 180.')
    return longitude


def _clean_radius(value):
    try:
        radius = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError('Radius must be a number.') from exc
    if radius <= 0:
        raise ValidationError('Radius must be greater than zero.')
    return radius


@transaction.atomic
def create_location(user, data):
    organization = _require_company_account(user)

    name = str(data.get('name') or '').strip()
    if not name:
        raise ValidationError('Location name is required.')
    if OfficeLocation.objects.filter(organization=organization, name__iexact=name).exists():
        raise ConflictError('An office location with this name already exists.')

    location = OfficeLocation(
        organization=organization,
        name=name,
        address=str(data.get('address') or '').strip(),
        latitude=_clean_latitude(data.get('latitude')),
        longitude=_clean_longitude(data.get('longitude')),
    )
    if data.get('radius_meters') is not None:
        location.radius_meters = _clean_radius(data['radius_meters'])

    location.save()
    return location


@transaction.atomic
def update_location(user, location_id, data):
    _require_company_account(user)
    location = get_location(user, location_id)

    if data.get('name') is not None:
        name = str(data['name']).strip()
        if not name:
            raise ValidationError('Location name is required.')
        location.name = name
    if data.get('address') is not None:
        location.address = str(data['address']).strip()
    if data.get('latitude') is not None:
        location.latitude = _clean_latitude(data['latitude'])
    if data.get('longitude') is not None:
        location.longitude = _clean_longitude(data['longitude'])
    if data.get('radius_meters') is not None:
        location.radius_meters = _clean_radius(data['radius_meters'])

    location.save()
    return location


@transaction.atomic
def deactivate_location(user, location_id):
    # Soft delete: attendance records reference the location via SET_NULL, so
    # deactivating preserves historical check-in data while removing it from the
    # active list used for check-in and settings.
    _require_company_account(user)
    location = get_location(user, location_id)
    location.is_active = False
    location.save(update_fields=['is_active', 'updated_at'])
    return location


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
