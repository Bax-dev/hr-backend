from django.db import models

from hr_app_backend.utils import TimeStampedModel


class EmployeeCustomField(TimeStampedModel):
    TYPE_TEXT = 'text'
    TYPE_NUMBER = 'number'
    TYPE_DATE = 'date'
    TYPE_BOOLEAN = 'boolean'
    FIELD_TYPES = [
        (TYPE_TEXT, 'Text'),
        (TYPE_NUMBER, 'Number'),
        (TYPE_DATE, 'Date'),
        (TYPE_BOOLEAN, 'Boolean'),
    ]

    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='custom_fields',
    )
    field_name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default=TYPE_TEXT)
    value = models.TextField(blank=True)

    class Meta:
        ordering = ['field_name']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'field_name'], name='unique_custom_field_name_per_employee'),
        ]

    def __str__(self):
        return self.field_name
