from django.urls import path

from .views import audit_log_list_view

app_name = 'audit_logs'
urlpatterns = [path('', audit_log_list_view, name='list')]
