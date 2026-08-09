from hr_app_backend.utils.request_ip import client_ip

from .models import AuditLog


def record_audit_event(*, organization, action, category, description, actor=None, request=None,
                       resource_type='', resource_id='', status=AuditLog.STATUS_SUCCESS, metadata=None):
    """Record an immutable organization event."""
    actor_name = ''
    actor_email = ''
    if actor is not None:
        actor_email = actor.email or ''
        profile = getattr(actor, 'profile', None)
        actor_name = (getattr(profile, 'full_name', '') or actor.get_full_name() or actor_email)
    ip_address = client_ip(request) if request else None
    return AuditLog.objects.create(
        organization=organization, actor=actor, actor_name=actor_name, actor_email=actor_email,
        action=action, category=category, description=description, resource_type=resource_type,
        resource_id=str(resource_id or ''), status=status, ip_address=ip_address,
        user_agent=request.headers.get('User-Agent', '') if request else '',
        request_id=getattr(request, 'request_id', '') if request else '', metadata=metadata or {},
    )


def record_audit_event_safely(**kwargs):
    """Best-effort recorder for request paths where audit storage must not mask the primary action."""
    try:
        return record_audit_event(**kwargs)
    except Exception:
        return None
