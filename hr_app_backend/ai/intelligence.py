"""Read-only HR intelligence used by the AI copilot tools."""

from collections import defaultdict
import datetime
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from hr_app_backend.attendance.models import AttendanceRecord
from hr_app_backend.employees.models import Employee
from hr_app_backend.leave.models import LeaveRequest
from hr_app_backend.platform.models import PayrollRecord
from hr_app_backend.talent.models import PerformanceReview
from hr_app_backend.utils import today_local
from hr_app_backend.utils.errors import PermissionDeniedError, ValidationError

from .permissions import is_company_admin, require_organization


def _month_bounds(month=None):
    today = today_local()
    if month:
        try:
            year, month_number = [int(part) for part in str(month).split('-')[:2]]
            start = datetime.date(year, month_number, 1)
        except (TypeError, ValueError) as exc:
            raise ValidationError('Month must be formatted as YYYY-MM.') from exc
    else:
        start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1)
    else:
        end = start.replace(month=start.month + 1, day=1)
    return start, end


def _employee_name(employee):
    return f'{employee.first_name} {employee.last_name}'.strip()


def _department_name(employee):
    if employee.department_record_id and employee.department_record:
        return employee.department_record.name
    return employee.department or ''


def _active_employees(organization):
    return (
        Employee.objects.filter(organization=organization)
        .exclude(status=Employee.STATUS_TERMINATED)
        .select_related('department_record', 'manager_employee')
    )


def _filter_department(queryset, department):
    term = (department or '').strip()
    if not term:
        return queryset
    return queryset.filter(
        Q(department__icontains=term) | Q(department_record__name__icontains=term)
    )


def _find_employees(organization, *, name=None, department=None, employee_id=None):
    queryset = _active_employees(organization)
    queryset = _filter_department(queryset, department)
    if employee_id:
        identity = Q(employee_id__iexact=str(employee_id))
        try:
            import uuid as uuid_lib

            uuid_lib.UUID(str(employee_id))
        except ValueError:
            pass
        else:
            identity |= Q(id=employee_id)
        queryset = queryset.filter(identity)
    term = (name or '').strip()
    if term:
        parts = term.split()
        name_query = (
            Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(email__icontains=term)
            | Q(employee_id__icontains=term)
        )
        if len(parts) >= 2:
            name_query |= Q(first_name__icontains=parts[0], last_name__icontains=parts[-1])
        queryset = queryset.filter(name_query)
    return list(queryset[:25])


def _scope_employees(user, employees):
    if is_company_admin(user):
        return employees
    profile = getattr(user, 'profile', None)
    linked = getattr(profile, 'employee', None) if profile else None
    if linked is None:
        raise PermissionDeniedError('Your account is not linked to an employee record.')
    return [employee for employee in employees if employee.id == linked.id]


def _serialize_employee(employee, extra=None):
    payload = {
        'id': str(employee.id),
        'employee_id': employee.employee_id,
        'name': _employee_name(employee),
        'email': employee.email,
        'department': _department_name(employee),
        'position': employee.position or '',
        'status': employee.status,
        'manager': (
            _employee_name(employee.manager_employee)
            if employee.manager_employee_id
            else employee.manager
        ),
        'hire_date': employee.hire_date.isoformat() if employee.hire_date else None,
    }
    if extra:
        payload.update(extra)
    return payload


def search_employees(user, *, name=None, department=None, employee_id=None):
    organization = require_organization(user)
    employees = _scope_employees(
        user,
        _find_employees(organization, name=name, department=department, employee_id=employee_id),
    )
    return {
        'count': len(employees),
        'employees': [_serialize_employee(employee) for employee in employees],
    }


def query_absences(user, *, min_count=3, month=None, department=None):
    organization = require_organization(user)
    start, end = _month_bounds(month)
    employees = _scope_employees(
        user,
        _find_employees(organization, department=department),
    )
    employee_ids = [employee.id for employee in employees]
    rows = (
        AttendanceRecord.objects.filter(
            organization=organization,
            employee_id__in=employee_ids,
            status=AttendanceRecord.STATUS_ABSENT,
            date__gte=start,
            date__lt=end,
        )
        .values('employee_id')
        .annotate(absent_count=Count('id'))
        .filter(absent_count__gte=max(int(min_count), 1))
        .order_by('-absent_count')
    )
    counts = {row['employee_id']: row['absent_count'] for row in rows}
    by_id = {employee.id: employee for employee in employees}
    matches = [
        _serialize_employee(by_id[employee_id], {'absent_count': absent_count})
        for employee_id, absent_count in counts.items()
        if employee_id in by_id
    ]
    return {
        'period': {'start': start.isoformat(), 'end': (end - timedelta(days=1)).isoformat()},
        'min_count': int(min_count),
        'count': len(matches),
        'employees': matches,
    }


def query_flight_risk(user, *, department=None):
    organization = require_organization(user)
    if not is_company_admin(user):
        raise PermissionDeniedError('Only company administrators can view flight-risk insights.')

    today = today_local()
    month_start, month_end = _month_bounds()
    employees = _find_employees(organization, department=department)
    employee_ids = [employee.id for employee in employees]

    absences = defaultdict(int)
    lates = defaultdict(int)
    for row in (
        AttendanceRecord.objects.filter(
            organization=organization,
            employee_id__in=employee_ids,
            date__gte=month_start,
            date__lt=month_end,
            status__in=[AttendanceRecord.STATUS_ABSENT, AttendanceRecord.STATUS_LATE],
        )
        .values('employee_id', 'status')
        .annotate(total=Count('id'))
    ):
        if row['status'] == AttendanceRecord.STATUS_ABSENT:
            absences[row['employee_id']] = row['total']
        else:
            lates[row['employee_id']] = row['total']

    rejected_leave = set(
        LeaveRequest.objects.filter(
            organization=organization,
            employee_id__in=employee_ids,
            status=LeaveRequest.STATUS_REJECTED,
            created_at__gte=timezone.now() - timedelta(days=90),
        ).values_list('employee_id', flat=True)
    )
    review_names = {
        review.employee_name.strip().lower(): review
        for review in PerformanceReview.objects.filter(organization=organization)
    }

    at_risk = []
    for employee in employees:
        reasons = []
        score = 0
        absent_count = absences.get(employee.id, 0)
        late_count = lates.get(employee.id, 0)
        if absent_count >= 3:
            score += 2
            reasons.append(f'{absent_count} absences this month')
        if late_count >= 5:
            score += 1
            reasons.append(f'{late_count} late arrivals this month')
        if employee.status == Employee.STATUS_ON_LEAVE:
            score += 1
            reasons.append('currently on leave')
        if employee.id in rejected_leave:
            score += 1
            reasons.append('recent rejected leave request')
        review = review_names.get(_employee_name(employee).lower())
        if review is None:
            if employee.hire_date and employee.hire_date <= today - timedelta(days=180):
                score += 1
                reasons.append('no recorded performance review')
        elif review.priority in {'high', 'critical'} or review.status in {'pending', 'draft'}:
            score += 1
            reasons.append(f'performance review is {review.status} ({review.priority} priority)')
        if score >= 2:
            at_risk.append(
                _serialize_employee(
                    employee,
                    {'risk_score': score, 'reasons': reasons, 'absent_count': absent_count, 'late_count': late_count},
                )
            )

    at_risk.sort(key=lambda item: item['risk_score'], reverse=True)
    return {
        'lookback_days': 90,
        'count': len(at_risk),
        'employees': at_risk[:20],
        'note': (
            'Flight risk is a heuristic from attendance, leave, and review signals. '
            'It is not a prediction of resignation.'
        ),
    }


def query_performance_drop(user, *, months=3, department=None):
    organization = require_organization(user)
    if not is_company_admin(user):
        raise PermissionDeniedError('Only company administrators can view performance-drop insights.')

    months = max(1, min(int(months), 12))
    today = today_local()
    recent_start = today - timedelta(days=30 * months)
    previous_start = recent_start - timedelta(days=30 * months)
    employees = _find_employees(organization, department=department)
    employee_ids = [employee.id for employee in employees]

    def _attendance_counts(start, end):
        counts = defaultdict(lambda: {'absent': 0, 'late': 0})
        for row in (
            AttendanceRecord.objects.filter(
                organization=organization,
                employee_id__in=employee_ids,
                date__gte=start,
                date__lt=end,
                status__in=[AttendanceRecord.STATUS_ABSENT, AttendanceRecord.STATUS_LATE],
            )
            .values('employee_id', 'status')
            .annotate(total=Count('id'))
        ):
            key = 'absent' if row['status'] == AttendanceRecord.STATUS_ABSENT else 'late'
            counts[row['employee_id']][key] = row['total']
        return counts

    recent = _attendance_counts(recent_start, today + timedelta(days=1))
    previous = _attendance_counts(previous_start, recent_start)
    review_by_name = defaultdict(list)
    for review in PerformanceReview.objects.filter(organization=organization):
        review_by_name[review.employee_name.strip().lower()].append(review)

    dropped = []
    for employee in employees:
        reasons = []
        recent_stats = recent.get(employee.id, {'absent': 0, 'late': 0})
        previous_stats = previous.get(employee.id, {'absent': 0, 'late': 0})
        if recent_stats['absent'] >= previous_stats['absent'] + 2 and recent_stats['absent'] >= 2:
            reasons.append(
                f"absences rose from {previous_stats['absent']} to {recent_stats['absent']}"
            )
        if recent_stats['late'] >= previous_stats['late'] + 3 and recent_stats['late'] >= 3:
            reasons.append(
                f"late arrivals rose from {previous_stats['late']} to {recent_stats['late']}"
            )
        reviews = review_by_name.get(_employee_name(employee).lower(), [])
        if any(review.priority in {'high', 'critical'} and review.status != 'completed' for review in reviews):
            reasons.append('open high-priority performance review')
        if any('drop' in (review.notes or '').lower() or 'decline' in (review.notes or '').lower() for review in reviews):
            reasons.append('review notes mention a performance decline')
        if reasons:
            dropped.append(
                _serialize_employee(
                    employee,
                    {
                        'reasons': reasons,
                        'recent_absences': recent_stats['absent'],
                        'previous_absences': previous_stats['absent'],
                        'recent_lates': recent_stats['late'],
                        'previous_lates': previous_stats['late'],
                    },
                )
            )

    return {
        'months': months,
        'recent_start': recent_start.isoformat(),
        'count': len(dropped),
        'employees': dropped[:20],
    }


def query_salary_reviews(user, *, within_days=45, department=None):
    organization = require_organization(user)
    if not is_company_admin(user):
        raise PermissionDeniedError('Only company administrators can view salary-review due lists.')

    today = today_local()
    window = max(1, min(int(within_days), 180))
    due = []
    for employee in _find_employees(organization, department=department):
        if employee.hire_date is None:
            continue
        anniversary = employee.hire_date.replace(year=today.year)
        if anniversary < today - timedelta(days=window):
            anniversary = employee.hire_date.replace(year=today.year + 1)
        days_until = (anniversary - today).days
        tenure_months = (today.year - employee.hire_date.year) * 12 + today.month - employee.hire_date.month
        if 0 <= days_until <= window or (tenure_months >= 11 and days_until <= window):
            due.append(
                _serialize_employee(
                    employee,
                    {
                        'hire_anniversary': anniversary.isoformat(),
                        'days_until_anniversary': days_until,
                        'tenure_months': tenure_months,
                        'current_salary': float(employee.salary) if employee.salary is not None else None,
                    },
                )
            )
    due.sort(key=lambda item: item['days_until_anniversary'])
    return {'within_days': window, 'count': len(due), 'employees': due[:25]}


def simulate_payroll_increment(user, *, percent, department=None):
    organization = require_organization(user)
    if not is_company_admin(user):
        raise PermissionDeniedError('Only company administrators can simulate payroll changes.')

    try:
        rate = Decimal(str(percent))
    except Exception as exc:
        raise ValidationError('Increment percent must be a number.') from exc
    if rate < 0 or rate > 100:
        raise ValidationError('Increment percent must be between 0 and 100.')

    employees = [employee for employee in _find_employees(organization, department=department) if employee.salary]
    current_total = sum((employee.salary for employee in employees), Decimal('0'))
    increase = (current_total * rate / Decimal('100')).quantize(Decimal('0.01'))
    new_total = current_total + increase
    breakdown = []
    for employee in employees[:25]:
        increment = (employee.salary * rate / Decimal('100')).quantize(Decimal('0.01'))
        breakdown.append(
            _serialize_employee(
                employee,
                {
                    'current_salary': float(employee.salary),
                    'increment': float(increment),
                    'new_salary': float(employee.salary + increment),
                },
            )
        )
    return {
        'percent': float(rate),
        'department': department or 'all',
        'employees_with_salary': len(employees),
        'current_monthly_payroll': float(current_total),
        'increase': float(increase),
        'new_monthly_payroll': float(new_total),
        'annual_increase': float((increase * 12).quantize(Decimal('0.01'))),
        'breakdown': breakdown,
    }


def get_employee_review_context(user, *, name=None, employee_id=None):
    organization = require_organization(user)
    matches = _scope_employees(
        user,
        _find_employees(organization, name=name, employee_id=employee_id),
    )
    if not matches:
        return {'error': 'No matching employee was found.', 'employees': []}
    if len(matches) > 1 and not employee_id:
        return {
            'error': 'Multiple employees matched. Ask the user which person they mean.',
            'employees': [_serialize_employee(employee) for employee in matches],
        }

    employee = matches[0]
    today = today_local()
    lookback = today - timedelta(days=90)
    attendance = list(
        AttendanceRecord.objects.filter(organization=organization, employee=employee, date__gte=lookback)
        .values('status')
        .annotate(total=Count('id'))
    )
    leaves = [
        {
            'type': item.leave_type,
            'status': item.status,
            'start_date': item.start_date.isoformat(),
            'end_date': item.end_date.isoformat(),
            'days': item.days,
            'reason': item.reason[:240],
        }
        for item in LeaveRequest.objects.filter(organization=organization, employee=employee)[:8]
    ]
    reviews = [
        {
            'cycle': item.review_cycle,
            'status': item.status,
            'priority': item.priority,
            'notes': (item.notes or '')[:500],
        }
        for item in PerformanceReview.objects.filter(
            organization=organization,
            employee_name__icontains=_employee_name(employee),
        )[:8]
    ]

    latest_payroll = (
        PayrollRecord.objects.filter(organization=organization, employee=employee)
        .order_by('-month')
        .first()
    )
    payload = _serialize_employee(employee)
    if is_company_admin(user) and employee.salary is not None:
        payload['salary'] = float(employee.salary)
    payload.update(
        {
            'attendance_last_90_days': {row['status']: row['total'] for row in attendance},
            'leave': leaves,
            'performance_reviews': reviews,
            'latest_payroll_month': latest_payroll.month if latest_payroll else None,
        }
    )
    return {'employee': payload}


def get_hr_insights(user, *, department=None):
    organization = require_organization(user)
    if not is_company_admin(user):
        raise PermissionDeniedError('Only company administrators can view organization-wide HR insights.')

    today = today_local()
    month_start, month_end = _month_bounds()
    employees = _find_employees(organization, department=department)
    employee_ids = [employee.id for employee in employees]
    present_today = AttendanceRecord.objects.filter(
        organization=organization,
        employee_id__in=employee_ids,
        date=today,
        status__in=[AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE],
    ).count()
    pending_leave = LeaveRequest.objects.filter(
        organization=organization,
        employee_id__in=employee_ids,
        status=LeaveRequest.STATUS_PENDING,
    ).count()
    open_reviews = PerformanceReview.objects.filter(organization=organization).exclude(
        status__in=['completed', 'closed', 'archived', 'approved']
    ).count()
    absences = query_absences(user, min_count=3, department=department)
    flight = query_flight_risk(user, department=department)
    salary = query_salary_reviews(user, department=department)
    drop = query_performance_drop(user, department=department)
    payroll_total = sum((employee.salary or Decimal('0') for employee in employees), Decimal('0'))

    alerts = []
    if absences['count']:
        alerts.append(f"{absences['count']} employee(s) have been absent 3+ times this month.")
    if flight['count']:
        alerts.append(f"{flight['count']} employee(s) show flight-risk signals.")
    if drop['count']:
        alerts.append(f"{drop['count']} employee(s) show a recent performance drop.")
    if salary['count']:
        alerts.append(f"{salary['count']} employee(s) are due for a salary review.")
    if pending_leave:
        alerts.append(f'{pending_leave} leave request(s) are waiting for review.')
    if open_reviews:
        alerts.append(f'{open_reviews} performance review(s) are still open.')

    return {
        'as_of': today.isoformat(),
        'department': department or 'all',
        'headcount': len(employees),
        'present_today': present_today,
        'pending_leave': pending_leave,
        'open_reviews': open_reviews,
        'monthly_salary_total': float(payroll_total),
        'period': {'start': month_start.isoformat(), 'end': (month_end - timedelta(days=1)).isoformat()},
        'alerts': alerts,
        'insights': {
            'high_absence': absences['employees'][:5],
            'flight_risk': flight['employees'][:5],
            'performance_drop': drop['employees'][:5],
            'salary_reviews_due': salary['employees'][:5],
        },
        'recommended_actions': [
            'Create a performance review cycle for teams with open or declining reviews.',
            'Follow up with high-absence employees and their managers.',
            'Schedule salary conversations for upcoming hire anniversaries.',
        ],
    }
