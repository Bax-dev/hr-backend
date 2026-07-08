from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.departments.models import Department
from hr_app_backend.utils import TimeStampedModel


class Team(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='teams')
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='teams',
    )
    name = models.CharField(max_length=150)
    lead = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'name'], name='unique_team_name_per_org'),
        ]

    def __str__(self):
        return self.name
