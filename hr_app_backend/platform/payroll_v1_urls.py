from django.urls import path

from .views import payroll_records_view, payroll_run_view, payroll_summary_view

urlpatterns = [
    path('', payroll_records_view, name='payroll-v1'),
    path('summary/', payroll_summary_view, name='payroll-summary-v1'),
    path('run/', payroll_run_view, name='payroll-run-v1'),
]
