from django.contrib import admin

from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'first_name', 'last_name', 'email', 'department', 'position', 'status', 'work_mode', 'organization')
    search_fields = ('employee_id', 'first_name', 'last_name', 'email')
    list_filter = ('status', 'work_mode', 'department')
