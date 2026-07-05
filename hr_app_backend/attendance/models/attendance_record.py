from django.db import models

from hr_app_backend.authentication.models import Organization
from hr_app_backend.employees.models import Employee
from hr_app_backend.utils import TimeStampedModel

from .office_location import OfficeLocation


class AttendanceRecord(TimeStampedModel):
    STATUS_PRESENT = 'present'
    STATUS_LATE = 'late'
    STATUS_ABSENT = 'absent'
    STATUS_EARLY_DEPARTURE = 'early_departure'
    STATUSES = [
        (STATUS_PRESENT, 'Present'),
        (STATUS_LATE, 'Late'),
        (STATUS_ABSENT, 'Absent'),
        (STATUS_EARLY_DEPARTURE, 'Early Departure'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='attendance_records')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    check_in = models.TimeField()
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_PRESENT)
    location = models.ForeignKey(OfficeLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name='attendance_records')
    # Coordinates reported by the device at punch time, kept for auditing.
    check_in_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_in_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    check_out_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ['-date', '-check_in']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'date'], name='unique_attendance_per_employee_per_day'),
        ]

    def __str__(self):
        return f'{self.employee} - {self.date} ({self.status})'
