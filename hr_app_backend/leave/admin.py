from django.contrib import admin

from .models import LeaveRequest


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'days', 'status', 'organization')
    search_fields = ('employee__first_name', 'employee__last_name', 'employee__employee_id', 'reason')
    list_filter = ('status', 'leave_type')

    def department(self, obj):
        return obj.employee.department

    department.short_description = 'Department'
