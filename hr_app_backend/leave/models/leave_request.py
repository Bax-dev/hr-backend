from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.employees.models import Employee
from hr_app_backend.utils import TimeStampedModel


class LeaveRequest(TimeStampedModel):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUSES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    TYPE_ANNUAL = 'Annual'
    TYPE_SICK = 'Sick'
    TYPE_MATERNITY = 'Maternity'
    TYPE_COMPASSIONATE = 'Compassionate'
    TYPE_UNPAID = 'Unpaid'
    TYPE_OTHER = 'Other'
    LEAVE_TYPES = [
        (TYPE_ANNUAL, 'Annual'),
        (TYPE_SICK, 'Sick'),
        (TYPE_MATERNITY, 'Maternity'),
        (TYPE_COMPASSIONATE, 'Compassionate'),
        (TYPE_UNPAID, 'Unpaid'),
        (TYPE_OTHER, 'Other'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='leave_requests')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=32, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.PositiveIntegerField(default=1)
    reason = models.TextField()
    rejection_reason = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_PENDING)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee} - {self.leave_type} ({self.status})'
