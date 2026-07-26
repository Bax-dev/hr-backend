from django.db import transaction

from hr_app_backend.departments.models import Department
from hr_app_backend.utils.errors import NotFoundError, ValidationError

from ..models import JobPosting, OffboardingPlan, OnboardingPlan, PerformanceReview
from .helpers import clean_text, require_organization, get_record


def get_public_job(job_id):
    """Look up a job posting for the public careers page (no auth, no org scoping).

    Draft postings are never publicly visible; anything else (e.g. Open,
    Closed) can be viewed by anyone holding the link.
    """
    try:
        job = JobPosting.objects.exclude(status__iexact='draft').get(pk=job_id)
    except (JobPosting.DoesNotExist, ValueError, TypeError) as exc:
        raise NotFoundError('Job posting not found.') from exc
    return job


def talent_summary(user):
    organization = require_organization(user)
    return {
        'jobs': JobPosting.objects.filter(organization=organization).count(),
        'open_jobs': JobPosting.objects.filter(organization=organization, status__iexact='open').count(),
        'onboarding': OnboardingPlan.objects.filter(organization=organization).count(),
        'performance': PerformanceReview.objects.filter(organization=organization).count(),
        'offboarding': OffboardingPlan.objects.filter(organization=organization).count(),
    }


def list_jobs(user):
    organization = require_organization(user)
    return JobPosting.objects.filter(organization=organization)


def get_job(user, job_id):
    organization = require_organization(user)
    return get_record(JobPosting, organization, job_id, 'Job posting')


def _normalize_department(organization, department_name):
    department = clean_text(department_name)
    if not department:
        return ''

    matched = Department.objects.filter(organization=organization, name__iexact=department).first()
    if matched is None:
        raise ValidationError('Select a department from your created departments list.')
    return matched.name


@transaction.atomic
def create_job(user, data):
    organization = require_organization(user)
    title = clean_text(data.get('title'))
    department = _normalize_department(organization, data.get('department'))
    location = clean_text(data.get('location'))
    job_type = clean_text(data.get('type'))
    status = clean_text(data.get('status')) or 'Open'
    if not all([title, department, location, job_type, status]):
        raise ValidationError('Title, department, location, employment type, and status are required.')

    return JobPosting.objects.create(
        organization=organization,
        title=title,
        department=department,
        location=location,
        type=job_type,
        status=status,
        description=clean_text(data.get('description')),
    )


@transaction.atomic
def update_job(user, job_id, data):
    job = get_job(user, job_id)
    for field in ('title', 'location', 'type', 'status', 'description'):
        if field in data:
            setattr(job, field, clean_text(data.get(field)))
    if 'department' in data:
        job.department = _normalize_department(job.organization, data.get('department'))
    if not all([job.title, job.department, job.location, job.type, job.status]):
        raise ValidationError('Title, department, location, employment type, and status are required.')
    job.save()
    return job


def delete_job(user, job_id):
    get_job(user, job_id).delete()
