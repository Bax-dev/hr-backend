import uuid

from django.db import models


def generate_uuid4():
    return str(uuid.uuid4())


class UUIDPrimaryKeyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
