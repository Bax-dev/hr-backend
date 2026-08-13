from ..services.permissions import highest_access_level


def serialize_file(file_asset, user=None):
    uploader = file_asset.uploaded_by
    return {
        'id': str(file_asset.id),
        'name': file_asset.name,
        'originalFilename': file_asset.original_filename,
        'folderId': str(file_asset.folder_id) if file_asset.folder_id else None,
        'contentType': file_asset.content_type,
        'sizeBytes': file_asset.size_bytes,
        'extension': file_asset.extension,
        'visibility': file_asset.visibility,
        'defaultAccess': file_asset.default_access,
        'uploadedBy': uploader.get_full_name() or uploader.email if uploader else None,
        'accessLevel': highest_access_level(user, file_asset) if user is not None else None,
        'createdAt': file_asset.created_at.isoformat(),
        'updatedAt': file_asset.updated_at.isoformat(),
    }


def serialize_share(share):
    grantee = share.employee or share.department
    grantee_type = 'employee' if share.employee_id else 'department'
    return {
        'id': str(share.id),
        'granteeType': grantee_type,
        'granteeId': str(grantee.id) if grantee else None,
        'granteeName': str(grantee) if grantee else None,
        'accessLevel': share.access_level,
        'createdAt': share.created_at.isoformat(),
    }
