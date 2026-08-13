from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel


class S3Configuration(TimeStampedModel):
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, 'Private'),
        (VISIBILITY_PUBLIC, 'Public'),
    ]

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name='s3_configuration'
    )
    bucket_name = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=64, blank=True)
    endpoint_url = models.URLField(max_length=500, blank=True)
    access_key_id = models.CharField(max_length=255, blank=True)
    # Fernet ciphertext; decrypted on demand via file_management.services.crypto.
    secret_access_key_encrypted = models.TextField(blank=True)
    default_visibility = models.CharField(
        max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE
    )
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f'S3 config for {self.organization.name}'
