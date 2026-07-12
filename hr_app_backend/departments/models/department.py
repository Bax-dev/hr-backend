from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel


class Department(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=150)
    manager = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default='#2563eb')

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'name'], name='unique_department_name_per_org'),
        ]

    def __str__(self):
        return self.name
