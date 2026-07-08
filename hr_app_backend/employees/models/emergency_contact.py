from django.db import models

from hr_app_backend.utils import TimeStampedModel


class EmployeeEmergencyContact(TimeStampedModel):
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='emergency_contacts',
    )
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=100)
    phone = models.CharField(max_length=32)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_primary', 'name']

    def __str__(self):
        return f'{self.name} ({self.relationship})'
