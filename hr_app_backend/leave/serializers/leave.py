def serialize_leave(leave):
    employee = leave.employee
    return {
        'id': leave.id,
        'employee_id': employee.id,
        'employee_name': f'{employee.first_name} {employee.last_name}'.strip(),
        'department': employee.department,
        'leave_type': leave.leave_type,
        'start_date': leave.start_date.isoformat(),
        'end_date': leave.end_date.isoformat(),
        'days': leave.days,
        'reason': leave.reason,
        'status': leave.get_status_display(),
        'created_at': leave.created_at.isoformat() if leave.created_at else None,
        'reviewed_at': leave.reviewed_at.isoformat() if leave.reviewed_at else None,
    }
