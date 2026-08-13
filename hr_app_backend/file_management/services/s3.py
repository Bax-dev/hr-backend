import boto3
from botocore.config import Config

from hr_app_backend.utils.env import get_env
from hr_app_backend.utils.errors import AppError, ValidationError

from .crypto import decrypt_secret

SOURCE_ORGANIZATION = 'organization'
SOURCE_PLATFORM = 'platform'


def platform_s3_client():
    """Client for the shared, env-configured bucket used when an org hasn't
    connected its own S3 bucket (also backs the legacy avatar/document
    presign flow in ``api.v1.views``)."""
    region = get_env('AWS_REGION', 'us-east-1').strip()
    endpoint_url = get_env('AWS_S3_ENDPOINT_URL', '').strip() or None
    return boto3.client(
        's3',
        region_name=region,
        endpoint_url=endpoint_url,
        config=Config(signature_version='s3v4'),
    )


def platform_bucket_name():
    bucket = get_env('AWS_STORAGE_BUCKET_NAME', '').strip()
    if not bucket:
        raise AppError('S3 upload is not configured on the server.', status_code=500)
    return bucket


def org_s3_client(config):
    return boto3.client(
        's3',
        region_name=(config.region or '').strip() or 'us-east-1',
        endpoint_url=(config.endpoint_url or '').strip() or None,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=decrypt_secret(config.secret_access_key_encrypted),
        config=Config(signature_version='s3v4'),
    )


def resolve_storage(organization):
    """Return ``(client, bucket_name, source)`` for uploads/downloads that
    belong to ``organization`` — its own bucket when configured and active,
    otherwise the platform's shared bucket."""
    config = getattr(organization, 's3_configuration', None)
    if config is not None and config.is_active and config.bucket_name and config.access_key_id:
        return org_s3_client(config), config.bucket_name, SOURCE_ORGANIZATION
    return platform_s3_client(), platform_bucket_name(), SOURCE_PLATFORM


def safe_folder_key(value):
    parts = [part for part in (value or '').strip().strip('/').split('/') if part]
    if any(part in {'.', '..'} for part in parts):
        raise ValidationError('Upload folder is invalid.')
    return '/'.join(parts)


def generate_upload_url(client, bucket, key, content_type, *, expires_in=900):
    return client.generate_presigned_url(
        'put_object',
        Params={'Bucket': bucket, 'Key': key, 'ContentType': content_type},
        ExpiresIn=expires_in,
    )


def generate_download_url(client, bucket, key, *, expires_in=300, filename=None, disposition='attachment'):
    params = {'Bucket': bucket, 'Key': key}
    if filename:
        params['ResponseContentDisposition'] = f'{disposition}; filename="{filename}"'
    return client.generate_presigned_url('get_object', Params=params, ExpiresIn=expires_in)


def test_connection(config):
    """Attempt to reach the configured bucket. Returns True or raises AppError."""
    if not config.bucket_name or not config.access_key_id:
        raise ValidationError('Bucket name and access key are required.')
    client = org_s3_client(config)
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        client.head_bucket(Bucket=config.bucket_name)
    except (BotoCoreError, ClientError) as exc:
        raise AppError(f'Could not reach the S3 bucket: {exc}', status_code=502) from exc
    return True
