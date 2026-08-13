from django.db import transaction

from hr_app_backend.audit_logs.services import record_audit_event_safely
from hr_app_backend.utils.errors import ValidationError

from ..models import S3Configuration
from .crypto import encrypt_secret
from .permissions import require_admin
from .s3 import test_connection as _test_connection


def _get_or_create(organization):
    config, _created = S3Configuration.objects.get_or_create(organization=organization)
    return config


def get_s3_settings(user):
    organization = require_admin(user)
    return _get_or_create(organization)


@transaction.atomic
def update_s3_settings(user, data, request=None):
    organization = require_admin(user)
    config = _get_or_create(organization)

    if 'bucket_name' in data or 'bucketName' in data:
        config.bucket_name = str(data.get('bucket_name', data.get('bucketName')) or '').strip()
    if 'region' in data:
        config.region = str(data.get('region') or '').strip()
    if 'endpoint_url' in data or 'endpointUrl' in data:
        config.endpoint_url = str(data.get('endpoint_url', data.get('endpointUrl')) or '').strip()
    if 'access_key_id' in data or 'accessKeyId' in data:
        config.access_key_id = str(data.get('access_key_id', data.get('accessKeyId')) or '').strip()
    if 'secret_access_key' in data or 'secretAccessKey' in data:
        secret = str(data.get('secret_access_key', data.get('secretAccessKey')) or '').strip()
        if secret:
            config.secret_access_key_encrypted = encrypt_secret(secret)
    if 'default_visibility' in data or 'defaultVisibility' in data:
        visibility = data.get('default_visibility', data.get('defaultVisibility'))
        if visibility not in dict(S3Configuration.VISIBILITY_CHOICES):
            raise ValidationError('Invalid default visibility.')
        config.default_visibility = visibility
    if 'is_active' in data or 'isActive' in data:
        is_active = bool(data.get('is_active', data.get('isActive')))
        if is_active and not (config.bucket_name and config.access_key_id and config.secret_access_key_encrypted):
            raise ValidationError('Bucket name, access key, and secret key are required before activating.')
        config.is_active = is_active

    config.save()
    record_audit_event_safely(
        organization=organization, actor=user, action='file_management.s3_settings_updated',
        category='file_management', description='Updated the organization S3 bucket configuration.',
        request=request,
    )
    return config


def test_s3_connection(user):
    organization = require_admin(user)
    config = _get_or_create(organization)
    return _test_connection(config)
