from django.urls import path

from .views import attendance_policy_view, company_view, security_view

urlpatterns = [
    path('company/', company_view, name='settings-company'),
    path('attendance-policy/', attendance_policy_view, name='settings-attendance-policy'),
    path('security/', security_view, name='settings-security'),
]
