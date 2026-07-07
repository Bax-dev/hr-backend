from django.urls import include, path

from .views import health_check

app_name = "v1"

urlpatterns = [
    path('attendance/', include('hr_app_backend.attendance.urls')),
    path('auth/', include('hr_app_backend.authentication.urls')),
    path('billing/', include('hr_app_backend.billing.urls')),
    path('employees/', include('hr_app_backend.employees.urls')),
    path('leave/', include('hr_app_backend.leave.urls')),
    path("health/", health_check, name="health-check"),
]
