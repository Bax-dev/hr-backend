from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel

from .base import TalentPriorityMixin, TalentStatusMixin


class LearningProgram(TimeStampedModel, TalentStatusMixin, TalentPriorityMixin):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='learning_programs')
    program_name = models.CharField(max_length=255)
    audience = models.CharField(max_length=255)
    owner = models.CharField(max_length=255)
    status = models.CharField(max_length=32, choices=TalentStatusMixin.STATUS_CHOICES, default=TalentStatusMixin.STATUS_DRAFT)
    priority = models.CharField(max_length=32, choices=TalentPriorityMixin.PRIORITY_CHOICES, default=TalentPriorityMixin.PRIORITY_MEDIUM)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['program_name']
