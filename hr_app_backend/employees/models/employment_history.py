from django.db import models

from hr_app_backend.utils import TimeStampedModel


class EmployeeEmploymentHistory(TimeStampedModel):
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='employment_history_entries',
    )
    company_name = models.CharField(max_length=255)
    job_title = models.CharField(max_length=150)
    employment_type = models.CharField(max_length=64, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    responsibilities = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date', '-created_at']

    def __str__(self):
        return f'{self.company_name} - {self.job_title}'
