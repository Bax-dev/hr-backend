from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.departments.models import Department
from hr_app_backend.utils import TimeStampedModel

from .designation import Designation
from .team import Team


class Employee(TimeStampedModel):
    STATUS_ACTIVE = 'active'
    STATUS_ON_LEAVE = 'on_leave'
    STATUS_TERMINATED = 'terminated'
    STATUSES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ON_LEAVE, 'On Leave'),
        (STATUS_TERMINATED, 'Terminated'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='employees')
    employee_id = models.CharField(max_length=32)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=32, blank=True)
    department = models.CharField(max_length=128, blank=True)
    department_record = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employees_by_record',
    )
    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='members',
    )
    position = models.CharField(max_length=128, blank=True)
    designation = models.ForeignKey(
        Designation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employees',
    )
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_ACTIVE)
    gender = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=64, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    avatar = models.URLField(blank=True)
    manager = models.CharField(max_length=255, blank=True)
    manager_employee = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='direct_reports',
    )
    # Tracks how many times the employee has self-edited their profile in the
    # current calendar month (period stored as 'YYYY-MM'). Used to enforce a
    # monthly self-service edit limit from the staff portal.
    self_edits_used = models.PositiveIntegerField(default=0)
    self_edits_period = models.CharField(max_length=7, blank=True)

    class Meta:
        ordering = ['first_name', 'last_name']
        constraints = [
            models.UniqueConstraint(fields=['organization', 'email'], name='unique_employee_email_per_org'),
            models.UniqueConstraint(fields=['organization', 'employee_id'], name='unique_employee_id_per_org'),
        ]

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.employee_id})'
