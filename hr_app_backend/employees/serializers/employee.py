def serialize_employee(employee):
    return {
        'id': employee.id,
        'employee_id': employee.employee_id,
        'first_name': employee.first_name,
        'last_name': employee.last_name,
        'email': employee.email,
        'phone': employee.phone,
        'department': employee.department,
        'department_record_id': employee.department_record_id,
        'position': employee.position,
        'designation_id': employee.designation_id,
        'designation_title': employee.designation.title if employee.designation else None,
        'team_id': employee.team_id,
        'team_name': employee.team.name if employee.team else None,
        'status': employee.status,
        'gender': employee.gender,
        'country': employee.country,
        'hire_date': employee.hire_date.isoformat() if employee.hire_date else None,
        'date_of_birth': employee.date_of_birth.isoformat() if employee.date_of_birth else None,
        'salary': float(employee.salary) if employee.salary is not None else None,
        'avatar': employee.avatar or None,
        'manager': employee.manager or None,
        'manager_employee_id': employee.manager_employee_id,
        'manager_employee_name': (
            f'{employee.manager_employee.first_name} {employee.manager_employee.last_name}'.strip()
            if employee.manager_employee
            else None
        ),
    }
