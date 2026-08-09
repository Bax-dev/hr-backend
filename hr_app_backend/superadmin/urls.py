from django.urls import path

from .views.audit_logs import superadmin_audit_log_list_view
from .views.companies import company_detail_view, company_list_view, company_status_view
from .views.dashboard import dashboard_overview_view
from .views.notifications import campaign_list_view
from .views.records import archived_records_view, employee_records_view
from .views.subscriptions import plan_summary_view, subscription_list_view
from .views.users import user_list_view

app_name = 'superadmin'

urlpatterns = [
    path('dashboard/', dashboard_overview_view, name='dashboard'),
    path('companies/', company_list_view, name='company-list'),
    path('companies/<uuid:org_id>/', company_detail_view, name='company-detail'),
    path('companies/<uuid:org_id>/status/', company_status_view, name='company-status'),
    path('users/', user_list_view, name='user-list'),
    path('subscriptions/', subscription_list_view, name='subscription-list'),
    path('plans/', plan_summary_view, name='plan-summary'),
    path('records/employees/', employee_records_view, name='employee-records'),
    path('records/archived/', archived_records_view, name='archived-records'),
    path('audit-logs/', superadmin_audit_log_list_view, name='audit-log-list'),
    path('notifications/campaigns/', campaign_list_view, name='notification-campaigns'),
]
