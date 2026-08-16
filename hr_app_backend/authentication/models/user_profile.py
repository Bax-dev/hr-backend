from django.conf import settings
from django.db import models

from hr_app_backend.utils import TimeStampedModel
from .organization import Organization


class UserProfile(TimeStampedModel):
    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_PREFER_NOT_TO_SAY = 'prefer_not_to_say'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
        (GENDER_PREFER_NOT_TO_SAY, 'Prefer not to say'),
    ]
    ACCOUNT_TYPE_COMPANY = 'company'
    ACCOUNT_TYPE_INDIVIDUAL = 'individual'
    ACCOUNT_TYPES = [
        (ACCOUNT_TYPE_COMPANY, 'Company'),
        (ACCOUNT_TYPE_INDIVIDUAL, 'Individual'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    invite_code = models.CharField(max_length=64, blank=True)
    organization = models.ForeignKey(Organization, null=True, blank=True, on_delete=models.SET_NULL, related_name='members')
    employee = models.OneToOneField(
        'employees.Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='user_profile',
    )
    must_change_password = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    gender = models.CharField(max_length=32, choices=GENDER_CHOICES, blank=True)
    country = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'{self.user.email} ({self.account_type})'
