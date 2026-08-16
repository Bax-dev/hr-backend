import datetime

from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel

DEFAULT_WORK_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri']


class WorkspaceSettings(TimeStampedModel):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name='workspace_settings'
    )

    # Company profile extras (name/email/phone/industry live on Organization).
    registration_number = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    headquarters_address = models.CharField(max_length=255, blank=True)
    website = models.CharField(max_length=255, blank=True)
    logo = models.URLField(max_length=500, blank=True)
    icon_logo = models.URLField(max_length=500, blank=True)

    # Attendance policy.
    standard_check_in = models.TimeField(default=datetime.time(hour=9, minute=0))
    standard_check_out = models.TimeField(default=datetime.time(hour=17, minute=0))
    grace_period_minutes = models.PositiveIntegerField(default=15)
    late_threshold_minutes = models.PositiveIntegerField(default=30)
    auto_check_out = models.BooleanField(default=False)
    work_days = models.JSONField(default=list)

    # Security settings.
    two_factor_required = models.BooleanField(default=False)
    password_expiry_days = models.PositiveIntegerField(default=90)
    session_timeout_minutes = models.PositiveIntegerField(default=60)
    enforce_single_session = models.BooleanField(default=False)
    allowed_email_domain = models.CharField(max_length=255, blank=True)

    # Workspace AI. When false, the HR Copilot button is hidden and the API
    # refuses assistant requests for everyone in this organization.
    copilot_enabled = models.BooleanField(default=True)

    def __str__(self):
        return f'Settings for {self.organization.name}'
