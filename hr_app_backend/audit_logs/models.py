from django.conf import settings
from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel


class AuditLog(TimeStampedModel):
    STATUS_SUCCESS = 'success'
    STATUS_FAILURE = 'failure'
    STATUS_CHOICES = [(STATUS_SUCCESS, 'Success'), (STATUS_FAILURE, 'Failure')]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs'
    )
    actor_name = models.CharField(max_length=255, blank=True)
    actor_email = models.EmailField(blank=True)
    action = models.CharField(max_length=120)
    category = models.CharField(max_length=64, db_index=True)
    resource_type = models.CharField(max_length=100, blank=True)
    resource_id = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=500)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SUCCESS, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at'], name='audit_org_created_idx'),
            models.Index(fields=['organization', 'action'], name='audit_org_action_idx'),
        ]

    def __str__(self):
        return f'{self.action}: {self.description}'
