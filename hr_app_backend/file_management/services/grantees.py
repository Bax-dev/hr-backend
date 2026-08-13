from hr_app_backend.departments.models import Department
from hr_app_backend.employees.models import Employee
from hr_app_backend.utils.errors import NotFoundError, ValidationError


def resolve_grantee(organization, data):
    """Resolve exactly one of employee_id/department_id from ``data`` into
    the corresponding ``(employee, department)`` pair, one of which is None."""
    employee_id = data.get('employee_id') or data.get('employeeId')
    department_id = data.get('department_id') or data.get('departmentId')
    if bool(employee_id) == bool(department_id):
        raise ValidationError('Provide exactly one of employee_id or department_id.')

    employee = None
    department = None
    if employee_id:
        try:
            employee = Employee.objects.get(organization=organization, pk=employee_id)
        except Employee.DoesNotExist as exc:
            raise NotFoundError('Employee not found.') from exc
    else:
        try:
            department = Department.objects.get(organization=organization, pk=department_id)
        except Department.DoesNotExist as exc:
            raise NotFoundError('Department not found.') from exc
    return employee, department
