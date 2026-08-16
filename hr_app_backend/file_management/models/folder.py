from django.conf import settings
from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.utils import TimeStampedModel


class Folder(TimeStampedModel):
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_ORGANIZATION = 'organization'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, 'Private'),
        (VISIBILITY_ORGANIZATION, 'Organization'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='file_folders')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='children'
    )
    name = models.CharField(max_length=255)
    # Private (default): only the creator, admins, and anyone with an explicit
    # FolderShare can see it — this is how a staff member's own folder stays
    # visible to just them and HR. Organization: everyone in the company can
    # browse it, same as an org-visible file.
    visibility = models.CharField(max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    # S3 object-key prefix (always trailing '/'), so the folder is visible in the
    # bucket and files uploaded into it land under the same path.
    storage_key = models.CharField(max_length=1024, blank=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'parent', 'name'], name='unique_folder_name_per_parent'
            ),
        ]

    def __str__(self):
        return self.name
