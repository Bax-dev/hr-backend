from django.db import models

from hr_app_backend.utils import TimeStampedModel


class Organization(TimeStampedModel):
    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32)
    size = models.CharField(max_length=32, blank=True)
    industry = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name
