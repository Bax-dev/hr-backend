from django.conf import settings
from django.db import models

from hr_app_backend.departments.models import Department
from hr_app_backend.employees.models import Employee
from hr_app_backend.utils import TimeStampedModel

from .folder import Folder


class FolderShare(TimeStampedModel):
    ACCESS_VIEW = 'view'
    ACCESS_MANAGE = 'manage'
    ACCESS_CHOICES = [
        (ACCESS_VIEW, 'View only'),
        (ACCESS_MANAGE, 'Manage'),
    ]

    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='shares')
    # Exactly one of employee/department is set; enforced in file_management.services.
    employee = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.CASCADE, related_name='folder_shares'
    )
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.CASCADE, related_name='folder_shares'
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
                name='folder_share_exactly_one_grantee',
            ),
            models.UniqueConstraint(
                fields=['folder', 'employee'], name='unique_folder_share_per_employee',
                condition=models.Q(employee__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['folder', 'department'], name='unique_folder_share_per_department',
                condition=models.Q(department__isnull=False),
            ),
        ]

    def __str__(self):
        grantee = self.employee or self.department
        return f'{self.folder.name} -> {grantee}'
