from django.db import transaction

from hr_app_backend.utils.errors import ValidationError

from ..models import OffboardingPlan, OnboardingPlan, PerformanceReview
from .helpers import clean_bool, clean_date, clean_priority, clean_status, clean_text, get_record, require_organization


def _list_records(user, model):
    organization = require_organization(user)
    return model.objects.filter(organization=organization)


def list_onboarding(user):
    return _list_records(user, OnboardingPlan)


def get_onboarding(user, record_pk):
    organization = require_organization(user)
    return get_record(OnboardingPlan, organization, record_pk, 'Onboarding plan')


@transaction.atomic
def create_onboarding(user, data):
    organization = require_organization(user)
    employee_name = clean_text(data.get('employee_name'))
    owner = clean_text(data.get('owner'))
    start_date = clean_date(data.get('start_date'), 'Start date')
    if len(employee_name) < 2:
        raise ValidationError('Employee name is required.')
    if len(owner) < 2:
        raise ValidationError('Owner is required.')
    if start_date is None:
        raise ValidationError('Start date is required.')
    return OnboardingPlan.objects.create(
        organization=organization,
        employee_name=employee_name,
        owner=owner,
        start_date=start_date,
        status=clean_status(data.get('status')),
        equipment_ready=clean_bool(data.get('equipment_ready')),
        notes=clean_text(data.get('notes')),
    )


@transaction.atomic
def update_onboarding(user, record_pk, data):
    record = get_onboarding(user, record_pk)
    if 'employee_name' in data:
        record.employee_name = clean_text(data.get('employee_name'))
    if 'owner' in data:
        record.owner = clean_text(data.get('owner'))
    if 'start_date' in data:
        record.start_date = clean_date(data.get('start_date'), 'Start date')
    if 'status' in data:
        record.status = clean_status(data.get('status'))
    if 'equipment_ready' in data:
        record.equipment_ready = clean_bool(data.get('equipment_ready'))
    if 'notes' in data:
        record.notes = clean_text(data.get('notes'))
    record.save()
    return record


def delete_onboarding(user, record_pk):
    get_onboarding(user, record_pk).delete()


def list_performance(user):
    return _list_records(user, PerformanceReview)


def get_performance(user, record_pk):
    organization = require_organization(user)
    return get_record(PerformanceReview, organization, record_pk, 'Performance review')


@transaction.atomic
def create_performance(user, data):
    organization = require_organization(user)
    employee_name = clean_text(data.get('employee_name'))
    review_cycle = clean_text(data.get('review_cycle'))
    owner = clean_text(data.get('owner'))
    if len(employee_name) < 2:
        raise ValidationError('Employee name is required.')
    if len(review_cycle) < 2:
        raise ValidationError('Review cycle is required.')
    if len(owner) < 2:
        raise ValidationError('Owner is required.')
    return PerformanceReview.objects.create(
        organization=organization,
        employee_name=employee_name,
        review_cycle=review_cycle,
        owner=owner,
        priority=clean_priority(data.get('priority')),
        status=clean_status(data.get('status')),
        notes=clean_text(data.get('notes')),
    )


@transaction.atomic
def update_performance(user, record_pk, data):
    record = get_performance(user, record_pk)
    if 'employee_name' in data:
        record.employee_name = clean_text(data.get('employee_name'))
    if 'review_cycle' in data:
        record.review_cycle = clean_text(data.get('review_cycle'))
    if 'owner' in data:
        record.owner = clean_text(data.get('owner'))
    if 'priority' in data:
        record.priority = clean_priority(data.get('priority'))
    if 'status' in data:
        record.status = clean_status(data.get('status'))
    if 'notes' in data:
        record.notes = clean_text(data.get('notes'))
    record.save()
    return record


def delete_performance(user, record_pk):
    get_performance(user, record_pk).delete()


def list_offboarding(user):
    return _list_records(user, OffboardingPlan)


def get_offboarding(user, record_pk):
    organization = require_organization(user)
    return get_record(OffboardingPlan, organization, record_pk, 'Offboarding plan')


@transaction.atomic
def create_offboarding(user, data):
    organization = require_organization(user)
    employee_name = clean_text(data.get('employee_name'))
    owner = clean_text(data.get('owner'))
    last_working_day = clean_date(data.get('last_working_day'), 'Last working day')
    if len(employee_name) < 2:
        raise ValidationError('Employee name is required.')
    if len(owner) < 2:
        raise ValidationError('Owner is required.')
    if last_working_day is None:
        raise ValidationError('Last working day is required.')
    return OffboardingPlan.objects.create(
        organization=organization,
        employee_name=employee_name,
        owner=owner,
        last_working_day=last_working_day,
        status=clean_status(data.get('status')),
        assets_cleared=clean_bool(data.get('assets_cleared')),
        notes=clean_text(data.get('notes')),
    )


@transaction.atomic
def update_offboarding(user, record_pk, data):
    record = get_offboarding(user, record_pk)
    if 'employee_name' in data:
        record.employee_name = clean_text(data.get('employee_name'))
    if 'owner' in data:
        record.owner = clean_text(data.get('owner'))
    if 'last_working_day' in data:
        record.last_working_day = clean_date(data.get('last_working_day'), 'Last working day')
    if 'status' in data:
        record.status = clean_status(data.get('status'))
    if 'assets_cleared' in data:
        record.assets_cleared = clean_bool(data.get('assets_cleared'))
    if 'notes' in data:
        record.notes = clean_text(data.get('notes'))
    record.save()
    return record


def delete_offboarding(user, record_pk):
    get_offboarding(user, record_pk).delete()
