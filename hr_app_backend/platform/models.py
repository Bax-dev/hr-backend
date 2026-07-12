from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.employees.models import Employee
from hr_app_backend.utils import TimeStampedModel


class Announcement(models.Model):
    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=255)
    content = models.TextField()
    author = models.CharField(max_length=255)
    priority = models.CharField(max_length=32, default='Normal')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']


class PayrollRecord(TimeStampedModel):
    STATUS_PENDING = 'Pending'
    STATUS_PROCESSING = 'Processing'
    STATUS_PAID = 'Paid'
    STATUSES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PAID, 'Paid'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='payroll_records')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_records')
    department = models.CharField(max_length=150, blank=True)
    month = models.CharField(max_length=7)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonuses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_PENDING)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-month', 'employee__first_name', 'employee__last_name']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'employee', 'month'],
                name='unique_payroll_record_per_employee_month',
            ),
        ]


class PlatformRecord(TimeStampedModel):
    MODULE_APPROVALS = 'approvals'
    MODULE_COMMUNICATIONS = 'communications'
    MODULE_ANALYTICS = 'analytics'
    MODULE_COMPLIANCE = 'compliance'
    MODULE_AI_FEATURES = 'ai-features'
    MODULE_NOTIFICATIONS = 'notifications'
    MODULE_INTEGRATIONS = 'integrations'
    MODULE_ADMIN_CONTROLS = 'admin-controls'
    MODULE_DASHBOARDS = 'dashboards'
    MODULES = [
        (MODULE_APPROVALS, 'Approvals'),
        (MODULE_COMMUNICATIONS, 'Communications'),
        (MODULE_ANALYTICS, 'Analytics'),
        (MODULE_COMPLIANCE, 'Compliance'),
        (MODULE_AI_FEATURES, 'AI Features'),
        (MODULE_NOTIFICATIONS, 'Notifications'),
        (MODULE_INTEGRATIONS, 'Integrations'),
        (MODULE_ADMIN_CONTROLS, 'Admin Controls'),
        (MODULE_DASHBOARDS, 'Dashboards'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='platform_records')
    module = models.CharField(max_length=32, choices=MODULES, db_index=True)
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ['-updated_at', '-created_at']
