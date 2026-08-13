from ..services.permissions import highest_folder_access_level


def serialize_folder(folder, user=None):
    creator = folder.created_by
    return {
        'id': str(folder.id),
        'name': folder.name,
        'parentId': str(folder.parent_id) if folder.parent_id else None,
        'visibility': folder.visibility,
        'createdBy': creator.get_full_name() or creator.email if creator else None,
        'accessLevel': highest_folder_access_level(user, folder) if user is not None else None,
        'createdAt': folder.created_at.isoformat(),
        'updatedAt': folder.updated_at.isoformat(),
    }


def serialize_folder_share(share):
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
