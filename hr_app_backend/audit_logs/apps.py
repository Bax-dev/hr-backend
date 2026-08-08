from django.apps import AppConfig


class AuditLogsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hr_app_backend.audit_logs'
    label = 'audit_logs'
