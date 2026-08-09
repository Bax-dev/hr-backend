from django.urls import include, path

from .views import health_check, upload_file_view, upload_presign_view

app_name = "v1"

urlpatterns = [
    path('audit-logs/', include('hr_app_backend.audit_logs.urls')),
    path('attendance/', include('hr_app_backend.attendance.urls')),
    path('auth/', include('hr_app_backend.authentication.urls')),
    path('billing/', include('hr_app_backend.billing.urls')),
    path('employees/', include('hr_app_backend.employees.urls')),
    path('leave/', include('hr_app_backend.leave.urls')),
    path('payroll/', include('hr_app_backend.platform.payroll_v1_urls')),
    path('talent/', include('hr_app_backend.talent.urls')),
    path('people/', include('hr_app_backend.people.urls')),
    path('settings/', include('hr_app_backend.workspace_settings.urls')),
    path('superadmin/', include('hr_app_backend.superadmin.urls')),
    path('uploads/presign/', upload_presign_view, name='upload-presign'),
    path('uploads/files/<path:key>/', upload_file_view, name='upload-file'),
    path('', include('hr_app_backend.platform.urls')),
    path("health/", health_check, name="health-check"),
]
