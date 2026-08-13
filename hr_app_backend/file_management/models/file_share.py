from django.conf import settings
from django.db import models

from hr_app_backend.departments.models import Department
from hr_app_backend.employees.models import Employee
from hr_app_backend.utils import TimeStampedModel

from .file_asset import FileAsset


class FileShare(TimeStampedModel):
    ACCESS_VIEW = 'view'
    ACCESS_DOWNLOAD = 'download'
    ACCESS_MANAGE = 'manage'
    ACCESS_CHOICES = [
        (ACCESS_VIEW, 'View only'),
        (ACCESS_DOWNLOAD, 'View and download'),
        (ACCESS_MANAGE, 'Manage'),
    ]

    file = models.ForeignKey(FileAsset, on_delete=models.CASCADE, related_name='shares')
    # Exactly one of employee/department is set; enforced in file_management.services.
    employee = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.CASCADE, related_name='file_shares'
    )
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.CASCADE, related_name='file_shares'
    )
    access_level = models.CharField(max_length=16, choices=ACCESS_CHOICES, default=ACCESS_VIEW)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(employee__isnull=False, department__isnull=True)
                    | models.Q(employee__isnull=True, department__isnull=False)
                ),
                name='file_share_exactly_one_grantee',
            ),
            models.UniqueConstraint(
                fields=['file', 'employee'], name='unique_file_share_per_employee',
                condition=models.Q(employee__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['file', 'department'], name='unique_file_share_per_department',
                condition=models.Q(department__isnull=False),
            ),
        ]

    def __str__(self):
        grantee = self.employee or self.department
        return f'{self.file.name} -> {grantee}'
