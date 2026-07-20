from django.urls import include, path

from hr_app_backend.employees.views import celebrations_view
from hr_app_backend.platform.views import (
    announcements_view,
    dashboard_attendance_trend_view,
    dashboard_overview_view,
    dashboard_recent_activity_view,
    dashboard_stats_view,
)
from hr_app_backend.talent.views import job_detail_view, jobs_view

from .docs import openapi_spec_view, swagger_ui_view

urlpatterns = [
    path('announcements', announcements_view, name='announcements'),
    path('announcements/', announcements_view, name='announcements-slash'),
    path('dashboard/overview', dashboard_overview_view, name='dashboard-overview'),
    path('dashboard/overview/', dashboard_overview_view, name='dashboard-overview-slash'),
    path('dashboard/stats', dashboard_stats_view, name='dashboard-stats'),
    path('dashboard/stats/', dashboard_stats_view, name='dashboard-stats-slash'),
    path('dashboard/attendance-trend', dashboard_attendance_trend_view, name='dashboard-attendance-trend'),
    path('dashboard/attendance-trend/', dashboard_attendance_trend_view, name='dashboard-attendance-trend-slash'),
    path('dashboard/recent-activity', dashboard_recent_activity_view, name='dashboard-recent-activity'),
    path('dashboard/recent-activity/', dashboard_recent_activity_view, name='dashboard-recent-activity-slash'),
    path('celebrations', celebrations_view, name='celebrations'),
    path('celebrations/', celebrations_view, name='celebrations-slash'),
    path('departments/', include('hr_app_backend.departments.urls')),
    path('jobs', jobs_view, name='jobs'),
    path('jobs/', include('hr_app_backend.talent.jobs_urls')),
    path('jobs/<int:job_id>', job_detail_view, name='job-detail'),
    path('payroll/', include('hr_app_backend.platform.payroll_urls')),
    path("docs/", swagger_ui_view, name="swagger-ui"),
    path("docs/openapi.yaml", openapi_spec_view, name="openapi-spec"),
    path("v1/", include(("hr_app_backend.api.v1.urls", "v1"), namespace="v1")),
]
