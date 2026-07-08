from django.db import models

from hr_app_backend.utils import TimeStampedModel


class EmployeeDocument(TimeStampedModel):
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=100)
    file_name = models.CharField(max_length=255, blank=True)
    file_url = models.URLField(blank=True)
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title
