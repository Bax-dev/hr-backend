from django.db.models import Q

from ..models import FileAsset, Folder
from .permissions import require_organization, user_can_access, user_can_access_folder

SEARCH_LIMIT = 8
CANDIDATE_LIMIT = 40


def _ancestor_paths(folders):
    """Map each folder id to ``[{id, name}, ...]`` from the root down to itself."""
    unique = []
    seen = set()
    for folder in folders:
        if folder is None or folder.id in seen:
            continue
        seen.add(folder.id)
        unique.append(folder)

    by_id = {folder.id: folder for folder in unique}
    pending = {folder.parent_id for folder in unique if folder.parent_id}

    while pending:
        missing = [pk for pk in pending if pk not in by_id]
        if not missing:
            break
        fetched = list(Folder.objects.filter(pk__in=missing).only('id', 'name', 'parent_id'))
        pending = set()
        for folder in fetched:
            by_id[folder.id] = folder
            if folder.parent_id:
                pending.add(folder.parent_id)

    paths = {}
    for folder in unique:
        chain = []
        node = folder
        visited = set()
        while node is not None and node.id not in visited:
            visited.add(node.id)
            chain.append({'id': str(node.id), 'name': node.name})
            node = by_id.get(node.parent_id) if node.parent_id else None
        chain.reverse()
        paths[folder.id] = chain
    return paths


def search_library(user, query, limit=SEARCH_LIMIT):
    """Find folders and S3-backed files the user can see, across the whole library."""
    organization = require_organization(user)
    term = (query or '').strip()
    if not term:
        return {'folders': [], 'files': [], 'folder_paths': {}, 'file_paths': {}}

    folder_candidates = list(
        Folder.objects.filter(organization=organization, name__icontains=term)
        .select_related('created_by')
        .prefetch_related('shares')[:CANDIDATE_LIMIT]
    )
    folders = [folder for folder in folder_candidates if user_can_access_folder(user, folder, 'view')][:limit]

    file_candidates = list(
        FileAsset.objects.filter(organization=organization, is_deleted=False)
        .filter(Q(name__icontains=term) | Q(original_filename__icontains=term))
        .select_related('uploaded_by', 'folder')
        .prefetch_related('shares')[:CANDIDATE_LIMIT]
    )
    files = [file_asset for file_asset in file_candidates if user_can_access(user, file_asset, 'view')][:limit]

    folder_paths = _ancestor_paths(folders)
    file_paths = _ancestor_paths([file_asset.folder for file_asset in files if file_asset.folder_id])

    return {
        'folders': folders,
        'files': files,
        'folder_paths': folder_paths,
        'file_paths': file_paths,
    }
