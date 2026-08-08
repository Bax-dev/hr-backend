from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from django.db.models import Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.models import UserProfile
from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.attendance.models import AttendanceRecord
from hr_app_backend.employees.models import Employee
from hr_app_backend.employees.services import get_my_employee
from hr_app_backend.employees.views.helpers import require_user
from hr_app_backend.leave.models import LeaveRequest
from hr_app_backend.utils.errors import AppError, NotFoundError, PermissionDeniedError, ValidationError
from hr_app_backend.utils.idempotency import idempotent
from hr_app_backend.utils.throttles import throttle_view

from .bulk_notifications import enqueue_bulk_notification
from .models import Announcement, BulkNotification, Notification, PayrollRecord, PersonalGoal, PlatformRecord
from .notifications_service import create_notification

PLATFORM_MODULE_CONFIG = {
    'approvals': {'list_key': 'approvals', 'item_key': 'approval'},
    'communications': {'list_key': 'communications', 'item_key': 'communication'},
    'analytics': {'list_key': 'reports', 'item_key': 'report'},
    'compliance': {'list_key': 'items', 'item_key': 'item'},
    'ai-features': {'list_key': 'features', 'item_key': 'feature'},
    'notifications': {'list_key': 'workflows', 'item_key': 'workflow'},
    'integrations': {'list_key': 'integrations', 'item_key': 'integration'},
    'admin-controls': {'list_key': 'controls', 'item_key': 'control'},
    'dashboards': {'list_key': 'dashboards', 'item_key': 'dashboard'},
    'inventory': {'list_key': 'inventory', 'item_key': 'item'},
}

INVENTORY_REMOVED_FIELDS = {'assetType', 'assettype', 'images'}


def _clean_platform_payload(module, payload):
    if module != 'inventory':
        return payload
    return {key: value for key, value in payload.items() if key not in INVENTORY_REMOVED_FIELDS}

DASHBOARD_STAT_COLORS = {
    'totalEmployees': {'accent': '#6F54FF', 'background': '#F2EDFF'},
    'presentToday': {'accent': '#10B981', 'background': '#E9FBF3'},
    'onLeave': {'accent': '#F59E0B', 'background': '#FFF6E7'},
    'newHires': {'accent': '#2563EB', 'background': '#EEF4FF'},
    'upcomingBirthdays': {'accent': '#EC4899', 'background': '#FFF0F7'},
}

DASHBOARD_DISTRIBUTION_COLORS = ['#2563EB', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#0EA5E9']


def _organization_for(request):
    user = require_user(request)
    organization = getattr(getattr(user, 'profile', None), 'organization', None)
    if organization is None:
        raise ValidationError('Your account is not linked to an organization.')
    return user, organization


def _is_individual_account(user):
    profile = getattr(user, 'profile', None)
    return getattr(profile, 'account_type', None) == UserProfile.ACCOUNT_TYPE_INDIVIDUAL


def _personal_user(request):
    user = require_user(request)
    if not _is_individual_account(user):
        raise PermissionDeniedError('Personal workspace tools are available to individual accounts only.')
    return user


def _serialize_personal_goal(goal):
    return {
        'id': str(goal.id),
        'title': goal.title,
        'completed': goal.completed,
        'priority': goal.priority,
        'category': goal.category,
        'dueDate': goal.due_date.isoformat() if goal.due_date else None,
        'completedAt': goal.completed_at.isoformat() if goal.completed_at else None,
        'createdAt': goal.created_at.isoformat(),
        'updatedAt': goal.updated_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(['GET'])
def personal_workspace_view(request):
    try:
        user = _personal_user(request)
        goals = PersonalGoal.objects.filter(user=user)
        return JsonResponse({'success': True, 'data': {
            'goals': [_serialize_personal_goal(goal) for goal in goals],
        }})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
def personal_goals_view(request):
    try:
        user = _personal_user(request)
        payload = parse_json_body(request)
        title = str(payload.get('title', '')).strip()
        if not title:
            raise ValidationError('Goal title is required.')
        if len(title) > 255:
            raise ValidationError('Goal title cannot exceed 255 characters.')
        profile = user.profile
        priority = str(payload.get('priority', PersonalGoal.PRIORITY_MEDIUM)).strip().lower()
        category = str(payload.get('category', '')).strip()
        due_date_value = str(payload.get('due_date', '')).strip()
        if priority not in dict(PersonalGoal.PRIORITIES):
            raise ValidationError('Priority must be low, medium, or high.')
        if len(category) > 80:
            raise ValidationError('Category cannot exceed 80 characters.')
        try:
            due_date = date.fromisoformat(due_date_value) if due_date_value else None
        except ValueError as exc:
            raise ValidationError('Due date must be a valid date.') from exc
        plan = profile.individual_plan or UserProfile.INDIVIDUAL_PLAN_FREE
        if plan == UserProfile.INDIVIDUAL_PLAN_FREE and (due_date or category or priority != PersonalGoal.PRIORITY_MEDIUM):
            raise PermissionDeniedError('Priority and due-date planning require Essential or Premium.')
        if plan != UserProfile.INDIVIDUAL_PLAN_PREMIUM and category:
            raise PermissionDeniedError('Custom goal categories require Premium.')
        goal_limits = {
            UserProfile.INDIVIDUAL_PLAN_FREE: 3,
            UserProfile.INDIVIDUAL_PLAN_ESSENTIAL: 25,
            UserProfile.INDIVIDUAL_PLAN_PREMIUM: None,
        }
        limit = goal_limits.get(profile.individual_plan or UserProfile.INDIVIDUAL_PLAN_FREE, 3)
        active_count = PersonalGoal.objects.filter(user=user, completed=False).count()
        if limit is not None and active_count >= limit:
            raise PermissionDeniedError(
                f'Your {profile.get_individual_plan_display() or "Free"} plan allows up to {limit} active goals.'
            )
        goal = PersonalGoal.objects.create(user=user, title=title, priority=priority, category=category, due_date=due_date)
        return JsonResponse({'success': True, 'data': {'goal': _serialize_personal_goal(goal)}}, status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['PATCH', 'DELETE'])
def personal_goal_detail_view(request, goal_pk):
    try:
        user = _personal_user(request)
        try:
            goal = PersonalGoal.objects.get(user=user, pk=goal_pk)
        except PersonalGoal.DoesNotExist as exc:
            raise NotFoundError('Personal goal not found.') from exc
        if request.method == 'DELETE':
            goal.delete()
            return JsonResponse({'success': True, 'message': 'Personal goal deleted.'})
        payload = parse_json_body(request)
        if 'title' in payload:
            title = str(payload['title']).strip()
            if not title or len(title) > 255:
                raise ValidationError('Goal title must be between 1 and 255 characters.')
            goal.title = title
        if 'completed' in payload:
            if not isinstance(payload['completed'], bool):
                raise ValidationError('Completed must be true or false.')
            goal.completed = payload['completed']
            goal.completed_at = timezone.now() if goal.completed else None
        goal.save()
        return JsonResponse({'success': True, 'data': {'goal': _serialize_personal_goal(goal)}})
    except AppError as exc:
        return error_response(exc)


def _require_company_account(user):
    """Reject individual/staff accounts from organization-wide admin actions."""
    if _is_individual_account(user):
        raise PermissionDeniedError('Only company administrators can perform this action.')


def _announcement_payload(data):
    title = str(data.get('title', '')).strip()
    content = str(data.get('content', '')).strip()
    priority = str(data.get('priority', 'Normal')).strip() or 'Normal'
    if len(title) < 3:
        raise ValidationError('Title is required.')
    if len(content) < 10:
        raise ValidationError('Content must be at least 10 characters.')
    return {'title': title, 'content': content, 'priority': priority}


def _serialize_announcement(announcement):
    return {
        'id': announcement.id,
        'title': announcement.title,
        'content': announcement.content,
        'author': announcement.author,
        'createdAt': announcement.created_at.isoformat(),
        'priority': announcement.priority,
    }


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def announcements_view(request):
    try:
        user, organization = _organization_for(request)
        if request.method == 'GET':
            records = Announcement.objects.filter(organization=organization)
            return JsonResponse([_serialize_announcement(record) for record in records], safe=False)

        payload = _announcement_payload(parse_json_body(request))
        author = getattr(getattr(user, 'profile', None), 'full_name', '') or user.get_full_name() or user.email
        announcement = Announcement.objects.create(
            organization=organization,
            author=author,
            **payload,
        )
        return JsonResponse(_serialize_announcement(announcement), status=201)
    except AppError as exc:
        return error_response(exc)


def _month_value(raw):
    value = (raw or '').strip()
    if not value:
        return timezone.now().date().strftime('%Y-%m')
    try:
        datetime.strptime(value, '%Y-%m')
    except ValueError as exc:
        raise ValidationError('Month must be in YYYY-MM format.') from exc
    return value


def _month_start(value):
    return datetime.strptime(value, '%Y-%m').date().replace(day=1)


def _month_end(value):
    start = _month_start(value)
    if start.month == 12:
        return date(start.year + 1, 1, 1) - timedelta(days=1)
    return date(start.year, start.month + 1, 1) - timedelta(days=1)


def _week_bounds(today):
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def _display_name(user):
    profile = getattr(user, 'profile', None)
    if profile and profile.full_name:
        return profile.full_name.split(' ', 1)[0]
    if user.get_full_name():
        return user.get_full_name().split(' ', 1)[0]
    return (user.email or 'there').split('@', 1)[0].title()


def _format_range_label(start, end):
    return f"{start.strftime('%d %b, %Y')} - {end.strftime('%d %b, %Y')}"


def _format_currency(value):
    return float(value.quantize(Decimal('0.01')))


def _safe_percentage(part, whole):
    if not whole:
        return 0
    return round((part / whole) * 100)


def _month_delta_label(current_value, previous_value, suffix='from last month'):
    if previous_value <= 0:
        if current_value <= 0:
            return ('neutral', f'0% {suffix}')
        return ('up', f'100% {suffix}')
    change = ((current_value - previous_value) / previous_value) * 100
    direction = 'up' if change > 0 else 'down' if change < 0 else 'neutral'
    return (direction, f'{abs(round(change))}% {suffix}')


def _next_occurrence(occasion, today):
    candidate = occasion.replace(year=today.year)
    if candidate < today:
        candidate = candidate.replace(year=today.year + 1)
    return candidate


def _birthday_events(employees, today, limit=2):
    upcoming = []
    for employee in employees:
        if not employee.date_of_birth:
            continue
        next_date = _next_occurrence(employee.date_of_birth, today)
        if next_date < today or next_date > today + timedelta(days=14):
            continue
        upcoming.append((next_date, employee))
    upcoming.sort(key=lambda item: item[0])
    return upcoming[:limit]


def _leave_event_candidates(organization, today, limit=2):
    return list(
        LeaveRequest.objects.filter(
            organization=organization,
            status=LeaveRequest.STATUS_APPROVED,
            start_date__gte=today,
            start_date__lte=today + timedelta(days=14),
        )
        .select_related('employee')
        .order_by('start_date', 'employee__first_name', 'employee__last_name')[:limit]
    )


def _dashboard_payroll_snapshot(employees, records):
    if records:
        total_payroll = sum(record.net_pay for record in records)
        total_deductions = sum(record.deductions for record in records)
        net_pay = total_payroll
        processed_count = sum(1 for record in records if record.status == PayrollRecord.STATUS_PAID)
        pending_count = len(records) - processed_count
        total_count = len(records)
    else:
        total_payroll = Decimal('0')
        total_deductions = Decimal('0')
        for employee in employees:
            base_salary = employee.salary or Decimal('0')
            bonus = Decimal('3500') if employee.department.strip().lower() == 'engineering' else Decimal('1500')
            deductions = (base_salary * Decimal('0.04')).quantize(Decimal('0.01'))
            total_deductions += deductions
            total_payroll += base_salary + bonus - deductions
        net_pay = total_payroll
        processed_count = 0
        pending_count = len(employees)
        total_count = len(employees)

    return {
        'totalPayroll': _format_currency(total_payroll),
        'totalDeductions': _format_currency(total_deductions),
        'netPay': _format_currency(net_pay),
        'processedPercent': _safe_percentage(processed_count, total_count),
        'pendingPercent': _safe_percentage(pending_count, total_count),
    }


def _dashboard_overview_payload(user, organization):
    today = timezone.localdate()
    week_start, week_end = _week_bounds(today)
    current_month = today.strftime('%Y-%m')
    previous_month_date = (today.replace(day=1) - timedelta(days=1))
    previous_month = previous_month_date.strftime('%Y-%m')
    month_start = _month_start(current_month)
    month_end = _month_end(current_month)

    active_employees = list(
        Employee.objects.filter(organization=organization).exclude(status=Employee.STATUS_TERMINATED)
    )
    employees_by_id = {employee.id: employee for employee in active_employees}
    employee_count = len(active_employees)

    attendance_today = list(
        AttendanceRecord.objects.filter(
            organization=organization,
            date=today,
            employee_id__in=employees_by_id.keys(),
        ).select_related('employee')
    )
    weekly_attendance = list(
        AttendanceRecord.objects.filter(
            organization=organization,
            date__range=(week_start, week_end),
            employee_id__in=employees_by_id.keys(),
        )
    )
    current_leaves = list(
        LeaveRequest.objects.filter(
            organization=organization,
            status=LeaveRequest.STATUS_APPROVED,
            start_date__lte=today,
            end_date__gte=today,
            employee_id__in=employees_by_id.keys(),
        ).select_related('employee')
    )
    monthly_leaves = list(
        LeaveRequest.objects.filter(
            organization=organization,
            status=LeaveRequest.STATUS_APPROVED,
            start_date__lte=month_end,
            end_date__gte=month_start,
            employee_id__in=employees_by_id.keys(),
        ).select_related('employee')
    )
    pending_leave_count = LeaveRequest.objects.filter(
        organization=organization,
        status=LeaveRequest.STATUS_PENDING,
        employee_id__in=employees_by_id.keys(),
    ).count()

    present_today = sum(
        1
        for record in attendance_today
        if record.status in {AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE, AttendanceRecord.STATUS_EARLY_DEPARTURE}
    )
    remote_today = sum(1 for record in attendance_today if record.location_id is None)
    on_leave_count = len({leave.employee_id for leave in current_leaves})
    absent_today = max(employee_count - present_today - on_leave_count, 0)

    new_hires_this_month = sum(
        1 for employee in active_employees if employee.hire_date and employee.hire_date.year == today.year and employee.hire_date.month == today.month
    )
    new_hires_last_month = sum(
        1
        for employee in active_employees
        if employee.hire_date and employee.hire_date.year == previous_month_date.year and employee.hire_date.month == previous_month_date.month
    )
    new_hires_direction, new_hires_note = _month_delta_label(new_hires_this_month, new_hires_last_month)

    current_birthdays = sum(
        1
        for employee in active_employees
        if employee.date_of_birth
        and today <= _next_occurrence(employee.date_of_birth, today) <= today + timedelta(days=6)
    )

    active_ids = {employee.id for employee in active_employees}
    previous_month_total = Employee.objects.filter(
        organization=organization,
        created_at__lt=month_start,
    ).exclude(status=Employee.STATUS_TERMINATED).count()
    total_direction, total_note = _month_delta_label(employee_count, previous_month_total)

    weekly_series = []
    weekly_present = weekly_absent = weekly_late = weekly_half_day = 0
    records_by_day = {week_start + timedelta(days=offset): [] for offset in range(7)}
    for record in weekly_attendance:
        records_by_day.setdefault(record.date, []).append(record)

    for day, records in records_by_day.items():
        present_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_PRESENT)
        late_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_LATE)
        half_day_count = sum(1 for record in records if record.status == AttendanceRecord.STATUS_EARLY_DEPARTURE)
        attended_count = present_count + late_count + half_day_count
        absent_count = max(employee_count - attended_count, 0)
        weekly_present += present_count
        weekly_absent += absent_count
        weekly_late += late_count
        weekly_half_day += half_day_count
        weekly_series.append({'day': day.strftime('%a'), 'value': attended_count})

    leave_type_map = {
        LeaveRequest.TYPE_ANNUAL: 'Annual Leave',
        LeaveRequest.TYPE_SICK: 'Sick Leave',
        LeaveRequest.TYPE_MATERNITY: 'Maternity Leave',
        LeaveRequest.TYPE_COMPASSIONATE: 'Compassionate Leave',
        LeaveRequest.TYPE_UNPAID: 'Unpaid Leave',
        LeaveRequest.TYPE_OTHER: 'Other Leave',
    }
    leave_color_map = {
        'Annual Leave': '#2563EB',
        'Sick Leave': '#10B981',
        'Casual Leave': '#F59E0B',
        'Maternity Leave': '#8B5CF6',
        'Other Leave': '#EC4899',
        'Compassionate Leave': '#F97316',
        'Unpaid Leave': '#64748B',
    }
    leave_totals = {}
    for leave in monthly_leaves:
        label = leave_type_map.get(leave.leave_type, 'Other Leave')
        if label == 'Compassionate Leave':
            label = 'Other Leave'
        leave_totals[label] = leave_totals.get(label, 0) + int(leave.days or 0)
    leave_breakdown = [
        {'name': name, 'value': value, 'color': leave_color_map.get(name, '#94A3B8')}
        for name, value in sorted(leave_totals.items(), key=lambda item: (-item[1], item[0]))
    ]
    total_leaves = sum(item['value'] for item in leave_breakdown)

    recent_employees = [
        {
            'id': str(employee.id),
            'name': f'{employee.first_name} {employee.last_name}'.strip(),
            'role': employee.position or 'Employee',
            'status': 'Active' if employee.status == Employee.STATUS_ACTIVE else employee.status.replace('_', ' ').title(),
            'joinedDate': employee.hire_date.isoformat() if employee.hire_date else employee.created_at.date().isoformat(),
            'initials': f"{(employee.first_name[:1] or '')}{(employee.last_name[:1] or '')}".upper() or 'NA',
            'avatar': employee.avatar or None,
        }
        for employee in sorted(
            active_employees,
            key=lambda item: item.hire_date or item.created_at.date(),
            reverse=True,
        )[:4]
    ]

    current_payroll_records = list(
        PayrollRecord.objects.filter(organization=organization, month=current_month).select_related('employee')
    )
    previous_payroll_records = list(PayrollRecord.objects.filter(organization=organization, month=previous_month))
    payroll_snapshot = _dashboard_payroll_snapshot(active_employees, current_payroll_records)
    previous_total_payroll = sum(record.net_pay for record in previous_payroll_records)
    payroll_direction, payroll_note = _month_delta_label(
        Decimal(str(payroll_snapshot['totalPayroll'])),
        previous_total_payroll,
        suffix='vs last month',
    )

    department_counts = {}
    for employee in active_employees:
        label = (employee.department_record.name if employee.department_record_id else employee.department) or 'Unassigned'
        department_counts[label] = department_counts.get(label, 0) + 1
    distribution_items = []
    for index, (label, value) in enumerate(sorted(department_counts.items(), key=lambda item: (-item[1], item[0]))[:6]):
        distribution_items.append({
            'name': label,
            'value': value,
            'percentage': _safe_percentage(value, employee_count),
            'color': DASHBOARD_DISTRIBUTION_COLORS[index % len(DASHBOARD_DISTRIBUTION_COLORS)],
            'icon': 'briefcase-business',
        })

    upcoming_events = []
    for next_date, employee in _birthday_events(active_employees, today):
        upcoming_events.append({
            'id': f'birthday-{employee.id}-{next_date.isoformat()}',
            'title': f"{employee.first_name} {employee.last_name}'s Birthday",
            'startsAt': datetime.combine(next_date, time(hour=9, minute=0), tzinfo=timezone.get_current_timezone()).isoformat(),
            'monthLabel': next_date.strftime('%b').upper(),
            'dayLabel': next_date.strftime('%d'),
            'color': '#EC4899',
        })
    for leave in _leave_event_candidates(organization, today):
        if len(upcoming_events) >= 3:
            break
        upcoming_events.append({
            'id': f'leave-{leave.id}',
            'title': f'{leave.employee.first_name} {leave.employee.last_name} leave starts',
            'startsAt': datetime.combine(leave.start_date, time(hour=9, minute=0), tzinfo=timezone.get_current_timezone()).isoformat(),
            'monthLabel': leave.start_date.strftime('%b').upper(),
            'dayLabel': leave.start_date.strftime('%d'),
            'color': '#10B981',
        })
    if len(upcoming_events) < 3:
        payroll_processing_date = min(month_end, today + timedelta(days=10))
        upcoming_events.append({
            'id': f'payroll-{current_month}',
            'title': 'Payroll Processing',
            'startsAt': datetime.combine(payroll_processing_date, time(hour=14, minute=0), tzinfo=timezone.get_current_timezone()).isoformat(),
            'monthLabel': payroll_processing_date.strftime('%b').upper(),
            'dayLabel': payroll_processing_date.strftime('%d'),
            'color': '#8B5CF6',
        })
    upcoming_events = sorted(upcoming_events, key=lambda item: item['startsAt'])[:3]

    total_colors = DASHBOARD_STAT_COLORS['totalEmployees']
    present_colors = DASHBOARD_STAT_COLORS['presentToday']
    leave_colors = DASHBOARD_STAT_COLORS['onLeave']
    hire_colors = DASHBOARD_STAT_COLORS['newHires']
    birthday_colors = DASHBOARD_STAT_COLORS['upcomingBirthdays']

    return {
        'header': {
            'title': 'Dashboard',
            'subtitle': f"Welcome back, {_display_name(user)}! Here's what's happening in your organization.",
            'dateRange': {
                'startDate': week_start.isoformat(),
                'endDate': week_end.isoformat(),
                'label': _format_range_label(week_start, week_end),
            },
            'notificationCount': pending_leave_count,
            'searchPlaceholder': 'Search employees, documents...',
        },
        'stats': [
            {
                'key': 'totalEmployees',
                'title': 'Total Employees',
                'value': str(employee_count),
                'note': total_note,
                'icon': 'users',
                'accentColor': total_colors['accent'],
                'backgroundColor': total_colors['background'],
                'trendDirection': total_direction,
            },
            {
                'key': 'presentToday',
                'title': 'Present Today',
                'value': str(present_today),
                'note': f"{_safe_percentage(present_today, employee_count)}% of total employees",
                'icon': 'user-check',
                'accentColor': present_colors['accent'],
                'backgroundColor': present_colors['background'],
                'trendDirection': 'neutral',
            },
            {
                'key': 'onLeave',
                'title': 'On Leave',
                'value': str(on_leave_count),
                'note': f"{_safe_percentage(on_leave_count, employee_count)}% of total employees",
                'icon': 'calendar-days',
                'accentColor': leave_colors['accent'],
                'backgroundColor': leave_colors['background'],
                'trendDirection': 'neutral',
            },
            {
                'key': 'newHires',
                'title': 'New Hires (This Month)',
                'value': str(new_hires_this_month),
                'note': new_hires_note,
                'icon': 'user-plus',
                'accentColor': hire_colors['accent'],
                'backgroundColor': hire_colors['background'],
                'trendDirection': new_hires_direction,
            },
            {
                'key': 'upcomingBirthdays',
                'title': 'Upcoming Birthdays',
                'value': str(current_birthdays),
                'note': 'This week',
                'icon': 'cake',
                'accentColor': birthday_colors['accent'],
                'backgroundColor': birthday_colors['background'],
                'trendDirection': 'neutral',
            },
        ],
        'attendanceOverview': {
            'rangeLabel': 'This Week',
            'series': weekly_series,
            'legend': [
                {'label': 'Present', 'value': weekly_present, 'color': '#22C55E'},
                {'label': 'Absent', 'value': weekly_absent, 'color': '#FF5D5D'},
                {'label': 'Late', 'value': weekly_late, 'color': '#F59E0B'},
                {'label': 'Half Day', 'value': weekly_half_day, 'color': '#3B82F6'},
            ],
        },
        'leaveSummary': {
            'rangeLabel': 'This Month',
            'totalLeaves': total_leaves,
            'breakdown': leave_breakdown,
        },
        'upcomingEvents': upcoming_events,
        'recentEmployees': recent_employees,
        'payrollOverview': {
            'rangeLabel': 'This Month',
            'totalPayroll': payroll_snapshot['totalPayroll'],
            'changeLabel': payroll_note,
            'changeDirection': payroll_direction,
            'totalDeductions': payroll_snapshot['totalDeductions'],
            'netPay': payroll_snapshot['netPay'],
            'processedPercent': payroll_snapshot['processedPercent'],
            'pendingPercent': payroll_snapshot['pendingPercent'],
        },
        'employeeDistribution': {
            'groupBy': 'By Department',
            'items': distribution_items,
        },
        'summary': {
            'presentToday': present_today,
            'absentToday': absent_today,
            'lateToday': sum(1 for record in attendance_today if record.status == AttendanceRecord.STATUS_LATE),
            'onLeave': on_leave_count,
            'remoteEmployees': remote_today,
            'pendingApprovals': pending_leave_count,
            'payrollThisMonth': payroll_snapshot['totalPayroll'],
        },
    }


def _active_employee_ids(organization):
    return list(
        Employee.objects.filter(organization=organization)
        .exclude(status=Employee.STATUS_TERMINATED)
        .values_list('id', flat=True)
    )


def _dashboard_stats_payload(organization):
    """Build the flat KPI block served by ``/api/dashboard/stats``.

    This is the same data as ``DashboardOverview.summary`` plus
    ``totalEmployees``, but computed with counts instead of materialising
    every employee, so the endpoint stays cheap enough to poll.
    """
    today = timezone.localdate()
    current_month = today.strftime('%Y-%m')
    employee_ids = _active_employee_ids(organization)
    employee_count = len(employee_ids)

    attendance_today = list(
        AttendanceRecord.objects.filter(
            organization=organization,
            date=today,
            employee_id__in=employee_ids,
        ).values_list('status', 'location_id')
    )
    attended_statuses = {
        AttendanceRecord.STATUS_PRESENT,
        AttendanceRecord.STATUS_LATE,
        AttendanceRecord.STATUS_EARLY_DEPARTURE,
    }
    present_today = sum(1 for status, _ in attendance_today if status in attended_statuses)
    late_today = sum(1 for status, _ in attendance_today if status == AttendanceRecord.STATUS_LATE)
    remote_today = sum(1 for _, location_id in attendance_today if location_id is None)

    on_leave = (
        LeaveRequest.objects.filter(
            organization=organization,
            status=LeaveRequest.STATUS_APPROVED,
            start_date__lte=today,
            end_date__gte=today,
            employee_id__in=employee_ids,
        )
        .values('employee_id')
        .distinct()
        .count()
    )
    pending_approvals = LeaveRequest.objects.filter(
        organization=organization,
        status=LeaveRequest.STATUS_PENDING,
        employee_id__in=employee_ids,
    ).count()

    payroll_this_month = PayrollRecord.objects.filter(
        organization=organization,
        month=current_month,
    ).aggregate(total=Sum('net_pay'))['total'] or Decimal('0')

    return {
        'totalEmployees': employee_count,
        'presentToday': present_today,
        'absentToday': max(employee_count - present_today - on_leave, 0),
        'lateToday': late_today,
        'onLeave': on_leave,
        'remoteEmployees': remote_today,
        'pendingApprovals': pending_approvals,
        'payrollThisMonth': _format_currency(payroll_this_month),
    }


def _attendance_trend_payload(organization):
    """Per-weekday present/late/absent counts for the current week."""
    today = timezone.localdate()
    week_start, week_end = _week_bounds(today)
    employee_ids = _active_employee_ids(organization)
    employee_count = len(employee_ids)

    buckets = {week_start + timedelta(days=offset): [] for offset in range(7)}
    records = AttendanceRecord.objects.filter(
        organization=organization,
        date__range=(week_start, week_end),
        employee_id__in=employee_ids,
    ).values_list('date', 'status')
    for record_date, status in records:
        buckets.setdefault(record_date, []).append(status)

    trend = []
    for day in sorted(buckets):
        statuses = buckets[day]
        present = sum(1 for status in statuses if status == AttendanceRecord.STATUS_PRESENT)
        late = sum(1 for status in statuses if status == AttendanceRecord.STATUS_LATE)
        half_day = sum(1 for status in statuses if status == AttendanceRecord.STATUS_EARLY_DEPARTURE)
        trend.append({
            'day': day.strftime('%a'),
            'present': present,
            'late': late,
            'absent': max(employee_count - present - late - half_day, 0),
        })
    return trend


def _relative_time(moment, now):
    """Render ``moment`` as a short human label such as ``3 hours ago``."""
    seconds = max(int((now - moment).total_seconds()), 0)
    if seconds < 60:
        return 'Just now'
    for unit_seconds, label in ((86400, 'day'), (3600, 'hour'), (60, 'minute')):
        if seconds >= unit_seconds:
            count = seconds // unit_seconds
            return f'{count} {label}{"s" if count > 1 else ""} ago'
    return 'Just now'


def _recent_activity_payload(organization, limit=10):
    """Merge hires, leave requests and check-ins into one reverse-chronological feed.

    Each source is capped at ``limit`` before merging, so the query cost stays
    bounded no matter how much history the organization has accumulated.
    """
    now = timezone.now()
    events = []

    for employee in (
        Employee.objects.filter(organization=organization)
        .exclude(status=Employee.STATUS_TERMINATED)
        .order_by('-created_at')[:limit]
    ):
        name = f'{employee.first_name} {employee.last_name}'.strip()
        events.append((employee.created_at, {
            'type': 'employee_joined',
            'message': f'{name} joined as {employee.position or "an employee"}',
            'employeeName': name,
            'avatar': employee.avatar or None,
        }))

    for leave in (
        LeaveRequest.objects.filter(organization=organization)
        .select_related('employee')
        .order_by('-created_at')[:limit]
    ):
        name = f'{leave.employee.first_name} {leave.employee.last_name}'.strip()
        events.append((leave.created_at, {
            'type': f'leave_{leave.status}',
            'message': f'{name}’s {leave.leave_type} leave request is {leave.status}',
            'employeeName': name,
            'avatar': leave.employee.avatar or None,
        }))

    for record in (
        AttendanceRecord.objects.filter(organization=organization)
        .select_related('employee')
        .order_by('-date', '-check_in')[:limit]
    ):
        name = f'{record.employee.first_name} {record.employee.last_name}'.strip()
        moment = datetime.combine(
            record.date,
            record.check_in,
            tzinfo=timezone.get_current_timezone(),
        )
        events.append((moment, {
            'type': 'attendance_check_in',
            'message': f'{name} checked in at {record.check_in.strftime("%I:%M %p").lstrip("0")}',
            'employeeName': name,
            'avatar': record.employee.avatar or None,
        }))

    events.sort(key=lambda item: item[0], reverse=True)
    return [
        {'id': index + 1, 'time': _relative_time(moment, now), **payload}
        for index, (moment, payload) in enumerate(events[:limit])
    ]


def _serialize_payroll_record(record):
    return {
        'id': str(record.id),
        'employee_id': str(record.employee_id),
        'employee_name': f'{record.employee.first_name} {record.employee.last_name}'.strip(),
        'department': record.department,
        'month': record.month,
        'base_salary': float(record.base_salary),
        'bonuses': float(record.bonuses),
        'deductions': float(record.deductions),
        'net_pay': float(record.net_pay),
        'status': record.status,
        'processed_at': record.processed_at.isoformat() if record.processed_at else None,
    }


def _payroll_summary(month, records):
    total_payroll = sum(record.net_pay for record in records)
    total_bonuses = sum(record.bonuses for record in records)
    total_deductions = sum(record.deductions for record in records)
    total_employees = len(records)
    average_salary = (total_payroll / total_employees) if total_employees else Decimal('0')
    return {
        'month': month,
        'total_payroll': float(total_payroll),
        'average_salary': float(average_salary),
        'total_bonuses': float(total_bonuses),
        'total_deductions': float(total_deductions),
        'total_employees': total_employees,
    }


def _build_payroll_record(organization, employee, month):
    base_salary = employee.salary or Decimal('0')
    bonuses = Decimal('3500') if employee.department.strip().lower() == 'engineering' else Decimal('1500')
    deductions = (base_salary * Decimal('0.04')).quantize(Decimal('0.01'))
    net_pay = base_salary + bonuses - deductions
    return PayrollRecord.objects.create(
        organization=organization,
        employee=employee,
        department=employee.department,
        month=month,
        base_salary=base_salary,
        bonuses=bonuses,
        deductions=deductions,
        net_pay=net_pay,
        status=PayrollRecord.STATUS_PROCESSING,
    )


@require_http_methods(['GET'])
def payroll_records_view(request):
    try:
        user, organization = _organization_for(request)
        month = _month_value(request.GET.get('month'))
        queryset = PayrollRecord.objects.filter(organization=organization, month=month).select_related('employee')
        if _is_individual_account(user):
            # Staff may only ever see their own payslip, never the rest of the org's.
            employee = get_my_employee(user)
            queryset = queryset.filter(employee=employee) if employee is not None else queryset.none()
        records = list(queryset)
        return JsonResponse({'success': True, 'data': {'records': [_serialize_payroll_record(record) for record in records]}})
    except AppError as exc:
        return error_response(exc)


@require_http_methods(['GET'])
def payroll_summary_view(request):
    try:
        user, organization = _organization_for(request)
        _require_company_account(user)
        month = _month_value(request.GET.get('month'))
        records = list(PayrollRecord.objects.filter(organization=organization, month=month))
        return JsonResponse({'success': True, 'data': {'summary': _payroll_summary(month, records)}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
@throttle_view('payroll:run', '10/min')
# Paying a workforce twice is the worst failure mode in this codebase, so a
# retried run must replay the first result rather than re-execute.
@idempotent('payroll:run')
def payroll_run_view(request):
    try:
        user, organization = _organization_for(request)
        _require_company_account(user)
        month = _month_value(parse_json_body(request).get('month'))
        employees = list(
            Employee.objects.filter(organization=organization).exclude(status=Employee.STATUS_TERMINATED)
        )
        if not employees:
            raise ValidationError('No employees are available for payroll.')

        existing_ids = set(
            PayrollRecord.objects.filter(organization=organization, month=month).values_list('employee_id', flat=True)
        )
        for employee in employees:
            if employee.id not in existing_ids:
                _build_payroll_record(organization, employee, month)
                # Let the employee know their payslip is ready to view/download.
                create_notification(
                    organization=organization,
                    recipient=employee,
                    title=f'Payslip ready for {month}',
                    body=f'Your payslip for {month} has been issued and is now available in the Payslips section.',
                    category=Notification.CATEGORY_PAYROLL,
                )

        records = list(
            PayrollRecord.objects.filter(organization=organization, month=month).select_related('employee')
        )
        return JsonResponse({
            'success': True,
            'message': 'Payroll run completed successfully.',
            'data': {'summary': _payroll_summary(month, records)},
        })
    except AppError as exc:
        return error_response(exc)


def _serialize_platform_record(record):
    payload = _clean_platform_payload(record.module, dict(record.payload))
    payload['id'] = str(record.id)
    if record.module == 'approvals':
        payload['updatedAt'] = record.updated_at.isoformat() if record.updated_at else None
    return payload


def _module_record(module, organization, record_pk):
    try:
        return PlatformRecord.objects.get(module=module, organization=organization, pk=record_pk)
    except PlatformRecord.DoesNotExist as exc:
        raise NotFoundError('Record not found.') from exc


def _list_response(module, organization):
    config = PLATFORM_MODULE_CONFIG[module]
    records = PlatformRecord.objects.filter(module=module, organization=organization)
    return JsonResponse({
        'success': True,
        'data': {config['list_key']: [_serialize_platform_record(record) for record in records]},
    })


def _create_response(module, organization, payload):
    config = PLATFORM_MODULE_CONFIG[module]
    record = PlatformRecord.objects.create(
        module=module,
        organization=organization,
        payload=_clean_platform_payload(module, payload),
    )
    return JsonResponse({'success': True, 'data': {config['item_key']: _serialize_platform_record(record)}}, status=201)


def _detail_response(module, organization, record_pk, payload=None):
    config = PLATFORM_MODULE_CONFIG[module]
    record = _module_record(module, organization, record_pk)
    if payload is not None:
        updated = dict(record.payload)
        updated.update(payload)
        record.payload = _clean_platform_payload(module, updated)
        record.save(update_fields=['payload', 'updated_at'])
    return JsonResponse({'success': True, 'data': {config['item_key']: _serialize_platform_record(record)}})


def _delete_response(module, organization, record_pk):
    _module_record(module, organization, record_pk).delete()
    return JsonResponse({'success': True, 'message': 'Record deleted successfully.'})


def _collection_view(request, module):
    user, organization = _organization_for(request)
    _require_company_account(user)
    if request.method == 'GET':
        return _list_response(module, organization)
    return _create_response(module, organization, parse_json_body(request))


def _detail_view(request, module, record_pk):
    user, organization = _organization_for(request)
    _require_company_account(user)
    if request.method == 'DELETE':
        return _delete_response(module, organization, record_pk)
    return _detail_response(module, organization, record_pk, parse_json_body(request))


@require_http_methods(['GET'])
def dashboard_overview_view(request):
    try:
        user, organization = _organization_for(request)
        _require_company_account(user)
        return JsonResponse(_dashboard_overview_payload(user, organization))
    except AppError as exc:
        return error_response(exc)


@require_http_methods(['GET'])
def dashboard_stats_view(request):
    try:
        user, organization = _organization_for(request)
        _require_company_account(user)
        return JsonResponse(_dashboard_stats_payload(organization))
    except AppError as exc:
        return error_response(exc)


@require_http_methods(['GET'])
def dashboard_attendance_trend_view(request):
    try:
        user, organization = _organization_for(request)
        _require_company_account(user)
        return JsonResponse(_attendance_trend_payload(organization), safe=False)
    except AppError as exc:
        return error_response(exc)


@require_http_methods(['GET'])
def dashboard_recent_activity_view(request):
    try:
        user, organization = _organization_for(request)
        _require_company_account(user)
        return JsonResponse(_recent_activity_payload(organization), safe=False)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def approvals_view(request):
    try:
        return _collection_view(request, 'approvals')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def approval_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'approvals', record_pk)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def communications_view(request):
    try:
        return _collection_view(request, 'communications')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def communication_detail_view(request, record_pk, module='communications'):
    try:
        return _detail_view(request, module, record_pk)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def analytics_view(request):
    try:
        return _collection_view(request, 'analytics')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def compliance_view(request):
    try:
        return _collection_view(request, 'compliance')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def compliance_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'compliance', record_pk)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def ai_features_view(request):
    try:
        return _collection_view(request, 'ai-features')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def inventory_view(request):
    try:
        return _collection_view(request, 'inventory')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def notifications_view(request):
    try:
        return _collection_view(request, 'notifications')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def notification_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'notifications', record_pk)
    except AppError as exc:
        return error_response(exc)


def _serialize_bulk_notification(campaign):
    return {
        'id': str(campaign.id),
        'title': campaign.title,
        'body': campaign.body,
        'status': campaign.status,
        'recipientCount': campaign.recipient_count,
        'sentCount': campaign.sent_count,
        'failedCount': campaign.failed_count,
        'createdAt': campaign.created_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(['POST'])
def bulk_notification_view(request):
    """Create inbox notifications and queue one email per active employee."""
    try:
        user, organization = _organization_for(request)
        _require_company_account(user)
        payload = parse_json_body(request)
        title = str(payload.get('title', '')).strip()
        body = str(payload.get('body', '')).strip()
        employee_ids = payload.get('employeeIds')
        if not title or len(title) > 255:
            raise ValidationError('Title is required and cannot exceed 255 characters.')
        if not body:
            raise ValidationError('Notification body is required.')
        if employee_ids is not None:
            if not isinstance(employee_ids, list) or not all(isinstance(value, str) for value in employee_ids):
                raise ValidationError('employeeIds must be a list of employee IDs.')
            try:
                employee_ids = list(dict.fromkeys(UUID(value) for value in employee_ids))
            except ValueError as exc:
                raise ValidationError('One or more employee IDs are invalid.') from exc

        campaign = enqueue_bulk_notification(
            organization=organization,
            created_by=user,
            title=title,
            body=body,
            employee_ids=employee_ids,
        )
        return JsonResponse(
            {'success': True, 'message': 'Notification queued for delivery.', 'data': {'campaign': _serialize_bulk_notification(campaign)}},
            status=202,
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET'])
def bulk_notification_status_view(request, campaign_pk):
    try:
        user, organization = _organization_for(request)
        _require_company_account(user)
        try:
            campaign = BulkNotification.objects.get(pk=campaign_pk, organization=organization)
        except BulkNotification.DoesNotExist as exc:
            raise NotFoundError('Notification campaign not found.') from exc
        return JsonResponse({'success': True, 'data': {'campaign': _serialize_bulk_notification(campaign)}})
    except AppError as exc:
        return error_response(exc)


def _serialize_notification(notification):
    return {
        'id': str(notification.id),
        'title': notification.title,
        'body': notification.body,
        'category': notification.category,
        'read': notification.read_at is not None,
        'readAt': notification.read_at.isoformat() if notification.read_at else None,
        'createdAt': notification.created_at.isoformat(),
    }


def _recipient_for(request):
    """Return ``(organization, employee)`` for the signed-in user's inbox.

    ``employee`` is ``None`` when the account has no linked employee record.
    """
    user = require_user(request)
    organization = getattr(getattr(user, 'profile', None), 'organization', None)
    return organization, get_my_employee(user)


@csrf_exempt
@require_http_methods(['GET'])
def notification_inbox_view(request):
    """List the signed-in user's personal notifications (newest first)."""
    try:
        organization, employee = _recipient_for(request)
        if employee is None:
            return JsonResponse({'success': True, 'data': {'notifications': [], 'unreadCount': 0}})

        notifications = list(
            Notification.objects.filter(organization=organization, recipient=employee)
        )
        unread_count = sum(1 for item in notifications if item.read_at is None)
        return JsonResponse({
            'success': True,
            'data': {
                'notifications': [_serialize_notification(item) for item in notifications],
                'unreadCount': unread_count,
            },
        })
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
def notification_inbox_read_all_view(request):
    """Mark all of the signed-in user's notifications as read."""
    try:
        organization, employee = _recipient_for(request)
        if employee is not None:
            Notification.objects.filter(
                organization=organization, recipient=employee, read_at__isnull=True
            ).update(read_at=timezone.now())
        return JsonResponse({'success': True, 'message': 'All notifications marked as read.'})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['POST'])
def notification_inbox_read_view(request, notification_pk):
    """Mark a single notification as read for the signed-in user."""
    try:
        organization, employee = _recipient_for(request)
        if employee is None:
            raise NotFoundError('Notification not found.')
        try:
            notification = Notification.objects.get(
                organization=organization, recipient=employee, pk=notification_pk
            )
        except Notification.DoesNotExist as exc:
            raise NotFoundError('Notification not found.') from exc

        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at', 'updated_at'])
        return JsonResponse({'success': True, 'data': {'notification': _serialize_notification(notification)}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def integrations_view(request):
    try:
        return _collection_view(request, 'integrations')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def integration_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'integrations', record_pk)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def admin_controls_view(request):
    try:
        return _collection_view(request, 'admin-controls')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def dashboards_view(request):
    try:
        return _collection_view(request, 'dashboards')
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'PUT', 'DELETE'])
def dashboard_detail_view(request, record_pk):
    try:
        return _detail_view(request, 'dashboards', record_pk)
    except AppError as exc:
        return error_response(exc)
