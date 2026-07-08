from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel


class Designation(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='designations')
    title = models.CharField(max_length=150)
    level = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['title']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'title'], name='unique_designation_title_per_org'),
        ]

    def __str__(self):
        return self.title
