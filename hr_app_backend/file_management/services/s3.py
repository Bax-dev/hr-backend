from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

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


def org_s3_config(organization):
    from ..models import S3Configuration

    try:
        return organization.s3_configuration
    except S3Configuration.DoesNotExist:
        return None


def resolve_storage(organization):
    """Return ``(client, bucket_name, source)`` for uploads/downloads that
    belong to ``organization`` — its own bucket when configured and active,
    otherwise the platform's shared bucket."""
    config = org_s3_config(organization)
    if config is not None and config.is_active and config.bucket_name and config.access_key_id:
        return org_s3_client(config), config.bucket_name, SOURCE_ORGANIZATION
    return platform_s3_client(), platform_bucket_name(), SOURCE_PLATFORM


def resolve_storage_if_configured(organization):
    """Like :func:`resolve_storage`, but returns ``(None, None, None)`` when
    neither an org bucket nor the platform bucket is available."""
    config = org_s3_config(organization)
    if config is not None and config.is_active and config.bucket_name and config.access_key_id:
        return org_s3_client(config), config.bucket_name, SOURCE_ORGANIZATION
    try:
        return platform_s3_client(), platform_bucket_name(), SOURCE_PLATFORM
    except AppError:
        return None, None, None


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

    try:
        client.head_bucket(Bucket=config.bucket_name)
    except (BotoCoreError, ClientError) as exc:
        raise AppError(f'Could not reach the S3 bucket: {exc}', status_code=502) from exc
    return True


def library_prefix(organization, source):
    """Root prefix for this organization's library in ``source``'s bucket."""
    if source == SOURCE_ORGANIZATION:
        return 'files/'
    return f'files/{organization.id}/'


def s3_segment(name):
    cleaned = (name or '').strip().replace('\\', '-').replace('\x00', '')
    if '/' in cleaned:
        raise ValidationError('Folder name cannot contain "/".')
    if not cleaned or cleaned in {'.', '..'}:
        raise ValidationError('Folder name is invalid.')
    return cleaned


def folder_prefix(folder, source):
    """S3 key prefix for ``folder``, always with a trailing slash."""
    parts = []
    node = folder
    seen = set()
    while node is not None:
        if node.id in seen:
            break
        seen.add(node.id)
        parts.append(s3_segment(node.name))
        node = node.parent if getattr(node, 'parent_id', None) else None
    parts.reverse()
    return library_prefix(folder.organization, source) + '/'.join(parts) + '/'


def object_key(organization, folder, filename, source):
    """Key for a new file: inside the folder prefix when nested, unique per upload."""
    prefix = folder.storage_key if folder and folder.storage_key else (
        folder_prefix(folder, source) if folder is not None else library_prefix(organization, source)
    )
    if prefix and not prefix.endswith('/'):
        prefix += '/'
    original = Path(str(filename or '').replace('\\', '/')).name
    stem = Path(original).stem.replace('\x00', '').strip('. ') or 'file'
    suffix = Path(original).suffix.lower()
    return f'{prefix}{stem}-{uuid4().hex[:8]}{suffix}'


def _normalize_prefix(prefix):
    key = (prefix or '').strip()
    if not key:
        return ''
    return key if key.endswith('/') else f'{key}/'


def put_folder_marker(client, bucket, prefix):
    key = _normalize_prefix(prefix)
    if not key:
        return
    client.put_object(Bucket=bucket, Key=key, Body=b'', ContentType='application/x-directory')


def ensure_prefix_chain(client, bucket, prefix):
    key = _normalize_prefix(prefix)
    if not key:
        return
    built = ''
    for part in key.strip('/').split('/'):
        built += f'{part}/'
        put_folder_marker(client, bucket, built)


def ensure_folder(organization, folder):
    """Create the S3 folder (and missing ancestors) for ``folder``."""
    client, bucket, source = resolve_storage_if_configured(organization)
    if client is None:
        return None
    prefix = folder_prefix(folder, source)
    try:
        ensure_prefix_chain(client, bucket, prefix)
    except (BotoCoreError, ClientError) as exc:
        raise AppError('Could not create the folder in S3.', status_code=502) from exc
    return prefix


def ensure_library_root(organization):
    client, bucket, source = resolve_storage_if_configured(organization)
    if client is None:
        return None
    prefix = library_prefix(organization, source)
    try:
        ensure_prefix_chain(client, bucket, prefix)
    except (BotoCoreError, ClientError) as exc:
        raise AppError('Could not create the folder in S3.', status_code=502) from exc
    return prefix


def delete_object(client, bucket, key):
    if not key:
        return
    try:
        client.delete_object(Bucket=bucket, Key=key)
    except (BotoCoreError, ClientError) as exc:
        raise AppError('Could not update the S3 bucket.', status_code=502) from exc


def copy_object(client, bucket, source_key, dest_key):
    if not source_key or not dest_key or source_key == dest_key:
        return
    client.copy_object(
        Bucket=bucket,
        CopySource={'Bucket': bucket, 'Key': source_key},
        Key=dest_key,
    )


def move_object(organization, source_key, dest_key):
    client, bucket, _source = resolve_storage(organization)
    if source_key == dest_key:
        return dest_key
    try:
        copy_object(client, bucket, source_key, dest_key)
        delete_object(client, bucket, source_key)
    except (BotoCoreError, ClientError) as exc:
        raise AppError('Could not move the file in S3.', status_code=502) from exc
    return dest_key


def delete_folder_prefix(organization, prefix):
    client, bucket, _source = resolve_storage_if_configured(organization)
    if client is None:
        return
    key = _normalize_prefix(prefix)
    try:
        delete_object(client, bucket, key)
    except AppError:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise AppError('Could not delete the folder in S3.', status_code=502) from exc


def move_prefix(organization, old_prefix, new_prefix):
    """Copy every object under ``old_prefix`` to ``new_prefix``, then delete the originals."""
    client, bucket, _source = resolve_storage_if_configured(organization)
    if client is None or old_prefix == new_prefix:
        return
    old_key = _normalize_prefix(old_prefix)
    new_key = _normalize_prefix(new_prefix)
    if not old_key or not new_key:
        return
    try:
        paginator = client.get_paginator('list_objects_v2')
        to_delete = []
        for page in paginator.paginate(Bucket=bucket, Prefix=old_key):
            for obj in page.get('Contents') or []:
                source_key = obj['Key']
                dest_key = new_key + source_key[len(old_key):]
                copy_object(client, bucket, source_key, dest_key)
                to_delete.append(source_key)
        for source_key in reversed(to_delete):
            dest_key = new_key + source_key[len(old_key):]
            if source_key != dest_key:
                delete_object(client, bucket, source_key)
        ensure_prefix_chain(client, bucket, new_key)
    except AppError:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise AppError('Could not move the folder in S3.', status_code=502) from exc
