from django.db import models

from .imports import date
from .ids import UUIDPrimaryKeyModel


class TimeStampedModel(UUIDPrimaryKeyModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_date = models.DateField(default=date.today, editable=False)

    class Meta:
        abstract = True
