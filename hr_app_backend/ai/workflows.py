"""Write actions the HR Copilot can execute against live HR records."""

from datetime import timedelta

from django.db import transaction

from hr_app_backend.platform.models import Notification
from hr_app_backend.platform.notifications_service import create_notification
from hr_app_backend.talent.models import PerformanceReview
from hr_app_backend.talent.models.base import TalentPriorityMixin, TalentStatusMixin
from hr_app_backend.utils.errors import ValidationError

from .intelligence import _department_name, _employee_name, _find_employees
from .permissions import require_company_admin


def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'true', '1', 'yes', 'on'}
    return bool(value)


def _parse_date(value, label):
    if not value:
        raise ValidationError(f'{label} is required.')
    try:
        from datetime import date

        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValidationError(f'{label} must be an ISO date (YYYY-MM-DD).') from exc


def _reviewer_for(employee, fallback):
    if employee.manager_employee_id:
        return _employee_name(employee.manager_employee)
    if employee.manager:
        return employee.manager
    return fallback or 'Manager'


def _notify_employee(employee, title, body, category=Notification.CATEGORY_GENERAL):
    create_notification(
        organization=employee.organization,
        recipient=employee,
        title=title,
        body=body,
        category=category,
    )
    manager = employee.manager_employee
    if manager is not None and manager.id != employee.id:
        create_notification(
            organization=employee.organization,
            recipient=manager,
            title=title,
            body=f'{_employee_name(employee)}: {body}',
            category=category,
        )


@transaction.atomic
def create_review_cycle(
    user,
    *,
    department,
    start_date,
    cycle_name=None,
    due_days=30,
    notify=True,
):
    organization = require_company_admin(user)
    department_name = (department or '').strip()
    if len(department_name) < 2:
        raise ValidationError('A department name is required to create a review cycle.')
    start = _parse_date(start_date, 'Start date')
    due = start + timedelta(days=max(7, min(int(due_days or 30), 120)))
    notify = _as_bool(notify, default=True)
    employees = _find_employees(organization, department=department_name)
    if not employees:
        raise ValidationError(f'No active employees were found in {department_name}.')

    actor = getattr(getattr(user, 'profile', None), 'full_name', '') or user.get_full_name() or user.email
    cycle = (cycle_name or '').strip() or f'{department_name} review — {start.isoformat()}'
    created = []
    for employee in employees:
        reviewer = _reviewer_for(employee, actor)
        notes = (
            f'Reviewer: {reviewer}\n'
            f'Start: {start.isoformat()}\n'
            f'Due: {due.isoformat()}\n'
            f'Department: {_department_name(employee) or department_name}\n'
            f'Assigned by HR Copilot for {actor}.'
        )
        existing = PerformanceReview.objects.filter(
            organization=organization,
            employee_name=_employee_name(employee),
            review_cycle=cycle,
        ).first()
        if existing:
            created.append({'id': str(existing.id), 'employee': _employee_name(employee), 'created': False})
            continue
        review = PerformanceReview.objects.create(
            organization=organization,
            employee_name=_employee_name(employee),
            review_cycle=cycle,
            priority=TalentPriorityMixin.PRIORITY_MEDIUM,
            status=TalentStatusMixin.STATUS_PENDING,
            notes=notes,
        )
        if notify:
            _notify_employee(
                employee,
                f'Performance review assigned: {cycle}',
                (
                    f'A performance review cycle has been opened for you starting {start.isoformat()}. '
                    f'Reviewer: {reviewer}. Please complete it by {due.isoformat()}.'
                ),
            )
        created.append(
            {
                'id': str(review.id),
                'employee': _employee_name(employee),
                'reviewer': reviewer,
                'created': True,
            }
        )

    new_count = sum(1 for item in created if item['created'])
    return {
        'cycle': cycle,
        'department': department_name,
        'start_date': start.isoformat(),
        'due_date': due.isoformat(),
        'employees_selected': len(employees),
        'reviews_created': new_count,
        'already_existed': len(created) - new_count,
        'notified': bool(notify),
        'reviews': created,
        'action': {
            'type': 'create_review_cycle',
            'label': f'Created {new_count} review(s) for {department_name}',
            'details': f'{cycle} · starts {start.isoformat()} · due {due.isoformat()}',
        },
    }


@transaction.atomic
def save_performance_review(user, *, name, review_text, cycle_name=None, employee_id=None):
    organization = require_company_admin(user)
    employees = _find_employees(organization, name=name, employee_id=employee_id)
    if not employees:
        raise ValidationError('No matching employee was found.')
    if len(employees) > 1 and not employee_id:
        raise ValidationError(
            'Multiple employees matched. Specify the full name or employee ID before saving a review.'
        )
    employee = employees[0]
    cycle = (cycle_name or '').strip() or f'AI review — {today_iso()}'
    notes = (review_text or '').strip()
    if len(notes) < 20:
        raise ValidationError('Review text is too short to save.')
    review = PerformanceReview.objects.create(
        organization=organization,
        employee_name=_employee_name(employee),
        review_cycle=cycle,
        priority=TalentPriorityMixin.PRIORITY_MEDIUM,
        status=TalentStatusMixin.STATUS_DRAFT,
        notes=notes[:4000],
    )
    return {
        'id': str(review.id),
        'employee': _employee_name(employee),
        'cycle': cycle,
        'status': review.status,
        'action': {
            'type': 'save_performance_review',
            'label': f'Saved a draft review for {_employee_name(employee)}',
            'details': cycle,
        },
    }


def today_iso():
    from hr_app_backend.utils import today_local

    return today_local().isoformat()


@transaction.atomic
def notify_employees(user, *, title, body, department=None, names=None):
    organization = require_company_admin(user)
    title = (title or '').strip()
    body = (body or '').strip()
    if len(title) < 3:
        raise ValidationError('A notification title is required.')
    if len(body) < 3:
        raise ValidationError('A notification message is required.')

    employees = []
    if department:
        employees.extend(_find_employees(organization, department=department))
    for name in names or []:
        employees.extend(_find_employees(organization, name=str(name)))
    unique = {employee.id: employee for employee in employees}
    recipients = list(unique.values())
    if not recipients:
        raise ValidationError('No matching employees were found to notify.')

    for employee in recipients:
        create_notification(
            organization=organization,
            recipient=employee,
            title=title[:255],
            body=body[:4000],
            category=Notification.CATEGORY_GENERAL,
        )
    return {
        'notified': len(recipients),
        'title': title,
        'recipients': [_employee_name(employee) for employee in recipients[:25]],
        'action': {
            'type': 'notify_employees',
            'label': f'Notified {len(recipients)} employee(s)',
            'details': title,
        },
    }
