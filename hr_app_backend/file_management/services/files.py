from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from django.db import transaction
from django.utils import timezone

from hr_app_backend.audit_logs.services import record_audit_event_safely
from hr_app_backend.utils.errors import AppError, NotFoundError, PermissionDeniedError, ValidationError

from ..models import FileAsset, FileShare
from . import s3 as s3_service
from .folders import get_folder
from .grantees import resolve_grantee
from .permissions import require_organization, user_can_access

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
ALLOWED_DOCUMENT_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain',
    'text/csv',
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
MAX_DOCUMENT_SIZE_BYTES = 25 * 1024 * 1024


def _validate_upload(content_type, size):
    if content_type in ALLOWED_IMAGE_TYPES:
        max_size = MAX_IMAGE_SIZE_BYTES
    elif content_type in ALLOWED_DOCUMENT_TYPES:
        max_size = MAX_DOCUMENT_SIZE_BYTES
    else:
        raise ValidationError(f'Unsupported file type "{content_type}".')

    try:
        size = int(size)
    except (TypeError, ValueError) as exc:
        raise ValidationError('File size is required.') from exc
    if size <= 0:
        raise ValidationError('File size must be greater than zero.')
    if size > max_size:
        raise ValidationError(f'File must not exceed {max_size // (1024 * 1024)} MB.')
    return size


@transaction.atomic
def presign_upload(user, data):
    organization = require_organization(user)
    filename = str(data.get('filename') or '').strip()
    content_type = str(data.get('content_type') or data.get('contentType') or '').strip()
    if not filename:
        raise ValidationError('Filename is required.')

    size = _validate_upload(content_type, data.get('file_size', data.get('fileSize')))

    folder = None
    folder_id = data.get('folder_id') or data.get('folderId')
    if folder_id:
        folder = get_folder(user, folder_id, level='manage')  # must be able to add content to this folder

    client, bucket, source = s3_service.resolve_storage(organization)
    if folder is not None:
        prefix = s3_service.ensure_folder(organization, folder)
        if prefix and folder.storage_key != prefix:
            folder.storage_key = prefix
            folder.save(update_fields=['storage_key'])
    else:
        s3_service.ensure_library_root(organization)

    key = s3_service.object_key(organization, folder, filename, source)

    try:
        url = s3_service.generate_upload_url(client, bucket, key, content_type)
    except (BotoCoreError, ClientError) as exc:
        raise AppError('Could not create the S3 upload URL.', status_code=502) from exc

    return {
        'method': 'PUT',
        'url': url,
        'headers': {'Content-Type': content_type},
        'key': key,
        'bucket': bucket,
        'source': source,
        'filename': filename,
        'content_type': content_type,
        'size': size,
    }


@transaction.atomic
def register_file(user, data, request=None):
    organization = require_organization(user)
    key = str(data.get('key') or '').strip()
    bucket = str(data.get('bucket') or '').strip()
    filename = str(data.get('filename') or '').strip()
    if not key or not bucket or not filename:
        raise ValidationError('key, bucket, and filename are required.')

    content_type = str(data.get('content_type') or data.get('contentType') or '').strip()
    size = _validate_upload(content_type, data.get('size', data.get('sizeBytes')))

    folder = None
    folder_id = data.get('folder_id') or data.get('folderId')
    if folder_id:
        folder = get_folder(user, folder_id, level='manage')

    _client, _bucket, source = s3_service.resolve_storage(organization)
    expected_prefix = (
        folder.storage_key
        if folder is not None and folder.storage_key
        else s3_service.library_prefix(organization, source)
    )
    if expected_prefix and not key.startswith(expected_prefix):
        raise ValidationError('Upload key does not match this folder.')

    default_visibility = FileAsset.VISIBILITY_PRIVATE
    config = s3_service.org_s3_config(organization)
    if config is not None and config.is_active:
        default_visibility = config.default_visibility

    name = str(data.get('name') or filename).strip() or filename

    file_asset = FileAsset.objects.create(
        organization=organization,
        folder=folder,
        name=name,
        original_filename=filename,
        storage_bucket=bucket,
        storage_key=key,
        content_type=content_type,
        size_bytes=size,
        extension=Path(filename).suffix.lower().lstrip('.'),
        visibility=default_visibility,
        default_access=FileAsset.ACCESS_DOWNLOAD,
        uploaded_by=user,
    )

    record_audit_event_safely(
        organization=organization, actor=user, action='file.uploaded', category='file_management',
        description=f'Uploaded "{file_asset.name}".', request=request,
        resource_type='file', resource_id=file_asset.id,
    )
    return file_asset


def list_files(user, folder_id=None, search=None):
    organization = require_organization(user)
    queryset = FileAsset.objects.filter(organization=organization, is_deleted=False)
    if folder_id:
        get_folder(user, folder_id)
        queryset = queryset.filter(folder_id=folder_id)
    else:
        queryset = queryset.filter(folder__isnull=True)
    if search:
        queryset = queryset.filter(name__icontains=search.strip())

    files = list(queryset.select_related('uploaded_by'))
    return [f for f in files if user_can_access(user, f, 'view')]


def get_file(user, file_pk, level='view'):
    organization = require_organization(user)
    try:
        file_asset = FileAsset.objects.get(organization=organization, pk=file_pk, is_deleted=False)
    except FileAsset.DoesNotExist as exc:
        raise NotFoundError('File not found.') from exc
    if not user_can_access(user, file_asset, level):
        raise PermissionDeniedError('You do not have permission to access this file.')
    return file_asset


@transaction.atomic
def update_file(user, file_pk, data, request=None):
    file_asset = get_file(user, file_pk, level='manage')

    if 'name' in data:
        name = str(data.get('name') or '').strip()
        if not name:
            raise ValidationError('File name is required.')
        file_asset.name = name

    if 'folder_id' in data or 'folderId' in data:
        folder_id = data.get('folder_id', data.get('folderId'))
        new_folder = get_folder(user, folder_id, level='manage') if folder_id else None
        new_folder_id = new_folder.id if new_folder is not None else None
        if new_folder_id != file_asset.folder_id:
            _client, _bucket, source = s3_service.resolve_storage(file_asset.organization)
            if new_folder is not None:
                prefix = s3_service.ensure_folder(file_asset.organization, new_folder)
                if prefix and new_folder.storage_key != prefix:
                    new_folder.storage_key = prefix
                    new_folder.save(update_fields=['storage_key'])
            dest_key = s3_service.object_key(
                file_asset.organization,
                new_folder,
                file_asset.original_filename or file_asset.name,
                source,
            )
            s3_service.move_object(file_asset.organization, file_asset.storage_key, dest_key)
            file_asset.storage_key = dest_key
        file_asset.folder = new_folder

    if 'visibility' in data:
        visibility = data.get('visibility')
        if visibility not in dict(FileAsset.VISIBILITY_CHOICES):
            raise ValidationError('Invalid visibility value.')
        file_asset.visibility = visibility

    if 'default_access' in data or 'defaultAccess' in data:
        access = data.get('default_access', data.get('defaultAccess'))
        if access not in dict(FileAsset.ACCESS_CHOICES):
            raise ValidationError('Invalid access value.')
        file_asset.default_access = access

    file_asset.save()
    record_audit_event_safely(
        organization=file_asset.organization, actor=user, action='file.updated', category='file_management',
        description=f'Updated "{file_asset.name}".', request=request,
        resource_type='file', resource_id=file_asset.id,
    )
    return file_asset


@transaction.atomic
def delete_file(user, file_pk, request=None):
    file_asset = get_file(user, file_pk, level='manage')
    client, bucket, _source = s3_service.resolve_storage_if_configured(file_asset.organization)
    if client is not None:
        s3_service.delete_object(client, bucket, file_asset.storage_key)
    file_asset.is_deleted = True
    file_asset.deleted_at = timezone.now()
    file_asset.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
    record_audit_event_safely(
        organization=file_asset.organization, actor=user, action='file.deleted', category='file_management',
        description=f'Deleted "{file_asset.name}".', request=request,
        resource_type='file', resource_id=file_asset.id,
    )


def resolve_download_url(user, file_pk, disposition='attachment'):
    # 'view' is enough to fetch the URL that backs the in-app preview iframe;
    # the frontend only *offers* a Download button when access_level is at
    # least 'download' (there is no way to let a browser render bytes without
    # also being able to save them, so the split is UI-level, not URL-level).
    file_asset = get_file(user, file_pk, level='view')
    return _presigned_download(file_asset, disposition=disposition)


def resolve_public_download_url(file_pk, disposition='attachment'):
    try:
        file_asset = FileAsset.objects.get(pk=file_pk, is_deleted=False, visibility=FileAsset.VISIBILITY_PUBLIC)
    except FileAsset.DoesNotExist as exc:
        raise NotFoundError('File not found.') from exc
    return _presigned_download(file_asset, disposition=disposition)


def _presigned_download(file_asset, disposition='attachment'):
    client, bucket, _source = s3_service.resolve_storage(file_asset.organization)
    try:
        return s3_service.generate_download_url(
            client, bucket, file_asset.storage_key,
            filename=file_asset.original_filename or file_asset.name,
            disposition=disposition,
        )
    except (BotoCoreError, ClientError) as exc:
        raise AppError('Could not retrieve the file from S3.', status_code=502) from exc


# ----- Shares ----------------------------------------------------------------

@transaction.atomic
def create_share(user, file_pk, data, request=None):
    file_asset = get_file(user, file_pk, level='manage')
    employee, department = resolve_grantee(file_asset.organization, data)

    access_level = data.get('access_level') or data.get('accessLevel') or FileShare.ACCESS_VIEW
    if access_level not in dict(FileShare.ACCESS_CHOICES):
        raise ValidationError('Invalid access level.')

    lookup = {'file': file_asset, 'employee': employee, 'department': department}
    share, _created = FileShare.objects.update_or_create(
        **lookup, defaults={'access_level': access_level, 'created_by': user}
    )
    record_audit_event_safely(
        organization=file_asset.organization, actor=user, action='file.shared', category='file_management',
        description=f'Shared "{file_asset.name}".', request=request,
        resource_type='file', resource_id=file_asset.id,
    )
    return share


def list_shares(user, file_pk):
    file_asset = get_file(user, file_pk, level='manage')
    return file_asset.shares.select_related('employee', 'department').all()


@transaction.atomic
def revoke_share(user, file_pk, share_pk, request=None):
    file_asset = get_file(user, file_pk, level='manage')
    try:
        share = file_asset.shares.get(pk=share_pk)
    except FileShare.DoesNotExist as exc:
        raise NotFoundError('Share not found.') from exc
    share.delete()
    record_audit_event_safely(
        organization=file_asset.organization, actor=user, action='file.unshared', category='file_management',
        description=f'Removed a share on "{file_asset.name}".', request=request,
        resource_type='file', resource_id=file_asset.id,
    )
