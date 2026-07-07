import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError

from ..models import Employee
from ..services import list_employees
from .helpers import require_user

DEFAULT_WINDOW_DAYS = 30


def _next_occurrence(anchor, today):
    """Next anniversary of `anchor` on or after `today` (Feb 29 → Feb 28)."""
    def on_year(year):
        try:
            return anchor.replace(year=year)
        except ValueError:
            return datetime.date(year, 2, 28)

    occurrence = on_year(today.year)
    if occurrence < today:
        occurrence = on_year(today.year + 1)
    return occurrence


def _celebration(employee, kind, occurrence, today, years=None):
    return {
        'id': f'{employee.pk}-{kind}',
        'employeeId': str(employee.pk),
        'employeeName': f'{employee.first_name} {employee.last_name}'.strip(),
        'department': employee.department,
        'position': employee.position,
        'type': kind,
        'date': occurrence.isoformat(),
        'daysUntil': (occurrence - today).days,
        'years': years,
        'avatar': employee.avatar or None,
    }


@csrf_exempt
@require_http_methods(['GET'])
def celebrations_view(request):
    try:
        user = require_user(request)

        try:
            window_days = int(request.GET.get('days', DEFAULT_WINDOW_DAYS))
        except (TypeError, ValueError):
            window_days = DEFAULT_WINDOW_DAYS
        if window_days <= 0:
            window_days = DEFAULT_WINDOW_DAYS

        today = datetime.date.today()
        cutoff = today + datetime.timedelta(days=window_days)
        celebrations = []

        employees = list_employees(user).exclude(status=Employee.STATUS_TERMINATED)
        for employee in employees:
            if employee.date_of_birth:
                occurrence = _next_occurrence(employee.date_of_birth, today)
                if occurrence <= cutoff:
                    celebrations.append(_celebration(employee, 'birthday', occurrence, today))

            if employee.hire_date:
                occurrence = _next_occurrence(employee.hire_date, today)
                years = occurrence.year - employee.hire_date.year
                if occurrence <= cutoff and years >= 1:
                    celebrations.append(
                        _celebration(employee, 'work_anniversary', occurrence, today, years=years)
                    )

        celebrations.sort(key=lambda item: (item['daysUntil'], item['employeeName']))
        return JsonResponse(celebrations, safe=False)
    except AppError as exc:
        return error_response(exc)
