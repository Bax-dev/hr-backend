from django.db import transaction

from hr_app_backend.utils.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError

from ..models import FileAsset, Folder, FolderShare
from . import s3 as s3_service
from .grantees import resolve_grantee
from .permissions import require_organization, user_can_access_folder


def _clean_name(value):
    name = (value or '').strip()
    if not name or len(name) > 255:
        raise ValidationError('Folder name is required and must be under 255 characters.')
    if '/' in name:
        raise ValidationError('Folder name cannot contain "/".')
    return name


def _storage_source(organization):
    _client, _bucket, source = s3_service.resolve_storage_if_configured(organization)
    return source or s3_service.SOURCE_PLATFORM


def _rewrite_keys_after_move(organization, old_prefix, new_prefix):
    if not old_prefix or old_prefix == new_prefix:
        return
    for item in Folder.objects.filter(organization=organization, storage_key__startswith=old_prefix):
        item.storage_key = new_prefix + item.storage_key[len(old_prefix):]
        item.save(update_fields=['storage_key'])
    for item in FileAsset.objects.filter(organization=organization, storage_key__startswith=old_prefix):
        item.storage_key = new_prefix + item.storage_key[len(old_prefix):]
        item.save(update_fields=['storage_key'])


def _get_parent(organization, parent_id, user=None, level='manage'):
    if not parent_id:
        return None
    try:
        parent = Folder.objects.get(organization=organization, pk=parent_id)
    except Folder.DoesNotExist as exc:
        raise NotFoundError('Parent folder not found.') from exc
    if user is not None and not user_can_access_folder(user, parent, level):
        raise NotFoundError('Parent folder not found.')
    return parent


def list_folders(user, parent_id=None, search=None):
    organization = require_organization(user)
    parent = _get_parent(organization, parent_id, user=user, level='view')
    folders = Folder.objects.filter(organization=organization, parent=parent)
    term = (search or '').strip()
    if term:
        folders = folders.filter(name__icontains=term)
    return [folder for folder in folders if user_can_access_folder(user, folder, 'view')]


def get_folder(user, folder_pk, level='view'):
    organization = require_organization(user)
    try:
        folder = Folder.objects.get(organization=organization, pk=folder_pk)
    except Folder.DoesNotExist as exc:
        raise NotFoundError('Folder not found.') from exc
    if not user_can_access_folder(user, folder, level):
        raise PermissionDeniedError('You do not have permission to access this folder.')
    return folder


@transaction.atomic
def create_folder(user, data):
    organization = require_organization(user)
    name = _clean_name(data.get('name'))
    # Creating inside a parent requires being able to manage that parent —
    # otherwise anyone who can merely *view* a shared folder could dump their
    # own folders into it. Root-level folders are open to any org member, so
    # every staff member can start their own private tree.
    parent = _get_parent(organization, data.get('parent_id') or data.get('parentId'), user=user, level='manage')

    visibility = data.get('visibility') or Folder.VISIBILITY_PRIVATE
    if visibility not in dict(Folder.VISIBILITY_CHOICES):
        raise ValidationError('Invalid visibility value.')

    if Folder.objects.filter(organization=organization, parent=parent, name__iexact=name).exists():
        raise ConflictError('A folder with this name already exists here.')

    folder = Folder(
        organization=organization, parent=parent, name=name, visibility=visibility, created_by=user,
    )
    folder.storage_key = s3_service.folder_prefix(folder, _storage_source(organization))
    folder.save()
    s3_service.ensure_folder(organization, folder)
    return folder


def _is_descendant(candidate, ancestor):
    node = candidate
    while node is not None:
        if node.id == ancestor.id:
            return True
        node = node.parent
    return False


@transaction.atomic
def update_folder(user, folder_pk, data):
    folder = get_folder(user, folder_pk, level='manage')

    new_parent = folder.parent
    if 'parent_id' in data or 'parentId' in data:
        parent_id = data.get('parent_id', data.get('parentId'))
        new_parent = _get_parent(folder.organization, parent_id, user=user, level='manage')
        if new_parent is not None and (new_parent.id == folder.id or _is_descendant(new_parent, folder)):
            raise ValidationError('A folder cannot be moved into itself or one of its own subfolders.')

    new_name = folder.name
    if 'name' in data:
        new_name = _clean_name(data.get('name'))

    duplicate = Folder.objects.filter(
        organization=folder.organization, parent=new_parent, name__iexact=new_name
    ).exclude(pk=folder.pk)
    if duplicate.exists():
        raise ConflictError('A folder with this name already exists here.')

    if 'visibility' in data:
        visibility = data.get('visibility')
        if visibility not in dict(Folder.VISIBILITY_CHOICES):
            raise ValidationError('Invalid visibility value.')
        folder.visibility = visibility

    old_prefix = folder.storage_key or s3_service.folder_prefix(folder, _storage_source(folder.organization))
    folder.parent = new_parent
    folder.name = new_name
    new_prefix = s3_service.folder_prefix(folder, _storage_source(folder.organization))
    if old_prefix != new_prefix:
        s3_service.move_prefix(folder.organization, old_prefix, new_prefix)
        folder.storage_key = new_prefix
        folder.save()
        _rewrite_keys_after_move(folder.organization, old_prefix, new_prefix)
    else:
        if not folder.storage_key:
            folder.storage_key = new_prefix
        folder.save()
    return folder


@transaction.atomic
def delete_folder(user, folder_pk):
    folder = get_folder(user, folder_pk, level='manage')
    if folder.children.exists() or folder.files.filter(is_deleted=False).exists():
        raise ConflictError('Only an empty folder can be deleted.')
    organization = folder.organization
    prefix = folder.storage_key
    folder.delete()
    if prefix:
        s3_service.delete_folder_prefix(organization, prefix)


# ----- Shares ----------------------------------------------------------------

@transaction.atomic
def create_folder_share(user, folder_pk, data):
    folder = get_folder(user, folder_pk, level='manage')
    employee, department = resolve_grantee(folder.organization, data)

    access_level = data.get('access_level') or data.get('accessLevel') or FolderShare.ACCESS_VIEW
    if access_level not in dict(FolderShare.ACCESS_CHOICES):
        raise ValidationError('Invalid access level.')

    lookup = {'folder': folder, 'employee': employee, 'department': department}
    share, _created = FolderShare.objects.update_or_create(
        **lookup, defaults={'access_level': access_level, 'created_by': user}
    )
    return share


def list_folder_shares(user, folder_pk):
    folder = get_folder(user, folder_pk, level='manage')
    return folder.shares.select_related('employee', 'department').all()


@transaction.atomic
def revoke_folder_share(user, folder_pk, share_pk):
    folder = get_folder(user, folder_pk, level='manage')
    try:
        share = folder.shares.get(pk=share_pk)
    except FolderShare.DoesNotExist as exc:
        raise NotFoundError('Share not found.') from exc
    share.delete()
