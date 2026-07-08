from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel

from .base import TalentStatusMixin


class OnboardingPlan(TimeStampedModel, TalentStatusMixin):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='onboarding_plans')
    employee_name = models.CharField(max_length=255)
    start_date = models.DateField()
    owner = models.CharField(max_length=255)
    status = models.CharField(max_length=32, choices=TalentStatusMixin.STATUS_CHOICES, default=TalentStatusMixin.STATUS_PENDING)
    equipment_ready = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['start_date', 'employee_name']
