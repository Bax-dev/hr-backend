def serialize_employee(employee):
    return {
        'id': employee.id,
        'employee_id': employee.employee_id,
        'first_name': employee.first_name,
        'last_name': employee.last_name,
        'email': employee.email,
        'phone': employee.phone,
        'department': employee.department,
        'position': employee.position,
        'status': employee.status,
        'gender': employee.gender,
        'country': employee.country,
        'hire_date': employee.hire_date.isoformat() if employee.hire_date else None,
        'salary': float(employee.salary) if employee.salary is not None else None,
        'avatar': employee.avatar or None,
        'manager': employee.manager or None,
    }
