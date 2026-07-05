from django.contrib import admin

from .models import AttendanceRecord, OfficeLocation


@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'latitude', 'longitude', 'radius_meters', 'is_active', 'organization')
    search_fields = ('name', 'address')
    list_filter = ('is_active',)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'check_in', 'check_out', 'status', 'location', 'organization')
    search_fields = ('employee__first_name', 'employee__last_name', 'employee__employee_id')
    list_filter = ('status', 'date', 'location')
