from django.urls import path

from .views import payroll_records_view, payroll_run_view, payroll_summary_view

urlpatterns = [
    path('', payroll_records_view, name='payroll'),
    path('summary', payroll_summary_view, name='payroll-summary'),
    path('run', payroll_run_view, name='payroll-run'),
]
