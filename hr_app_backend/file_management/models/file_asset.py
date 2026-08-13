from django.conf import settings
from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel

from .folder import Folder


class FileAsset(TimeStampedModel):
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_ORGANIZATION = 'organization'
    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, 'Private'),
        (VISIBILITY_ORGANIZATION, 'Organization'),
        (VISIBILITY_PUBLIC, 'Public'),
    ]

    ACCESS_VIEW = 'view'
    ACCESS_DOWNLOAD = 'download'
    ACCESS_CHOICES = [
        (ACCESS_VIEW, 'View only'),
        (ACCESS_DOWNLOAD, 'View and download'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='files')
    folder = models.ForeignKey(
        Folder, null=True, blank=True, on_delete=models.CASCADE, related_name='files'
    )
    name = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255, blank=True)
    storage_bucket = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=1024)
    content_type = models.CharField(max_length=150, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    extension = models.CharField(max_length=20, blank=True)
    visibility = models.CharField(max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    default_access = models.CharField(max_length=16, choices=ACCESS_CHOICES, default=ACCESS_DOWNLOAD)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['organization', 'folder', 'is_deleted']),
        ]

    def __str__(self):
        return self.name
