def serialize_audit_log(log):
    return {
        'id': str(log.id), 'action': log.action, 'category': log.category,
        'description': log.description, 'status': log.status,
        'organization': {'id': str(log.organization_id), 'name': getattr(log.organization, 'name', '')},
        'actor': {'id': str(log.actor_id) if log.actor_id else None, 'name': log.actor_name, 'email': log.actor_email},
        'resource': {'type': log.resource_type, 'id': log.resource_id},
        'ipAddress': log.ip_address, 'userAgent': log.user_agent, 'requestId': log.request_id,
        'metadata': log.metadata, 'createdAt': log.created_at.isoformat(),
    }
