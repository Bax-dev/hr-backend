from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel

from .base import TalentPriorityMixin, TalentStatusMixin


class PerformanceReview(TimeStampedModel, TalentStatusMixin, TalentPriorityMixin):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='performance_reviews')
    employee_name = models.CharField(max_length=255)
    review_cycle = models.CharField(max_length=150)
    priority = models.CharField(max_length=32, choices=TalentPriorityMixin.PRIORITY_CHOICES, default=TalentPriorityMixin.PRIORITY_MEDIUM)
    status = models.CharField(max_length=32, choices=TalentStatusMixin.STATUS_CHOICES, default=TalentStatusMixin.STATUS_PENDING)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['employee_name', 'review_cycle']
