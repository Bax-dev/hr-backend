from django.conf import settings


def client_ip(request):
    
    forwarded = request.headers.get('X-Forwarded-For', '')
    hops = settings.TRUSTED_PROXY_HOPS
    if forwarded and hops > 0:
        parts = [part.strip() for part in forwarded.split(',') if part.strip()]
        index = len(parts) - hops
        if 0 <= index < len(parts):
            return parts[index]
    return request.META.get('REMOTE_ADDR', 'unknown')
