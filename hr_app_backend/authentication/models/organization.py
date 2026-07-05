from django.db import models

from hr_app_backend.utils import TimeStampedModel


class Organization(TimeStampedModel):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32)
    size = models.CharField(max_length=32, blank=True)
    industry = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.name
