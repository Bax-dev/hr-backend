"""Where a request comes from, for session and sign-in history rows.

Deliberately simple (no user-agent database, no geo-IP).
"""

import ipaddress
import re

from hr_app_backend.utils.request_ip import client_ip as request_client_ip


def parse_user_agent(user_agent):
    """Returns ``(device, browser)``."""
    ua = user_agent or ''
    if not ua.strip():
        return 'Unknown device', 'Browser'
    if 'Edg/' in ua:
        browser = 'Edge'
    elif 'Chrome/' in ua:
        browser = 'Chrome'
    elif 'Firefox/' in ua:
        browser = 'Firefox'
    elif 'Safari/' in ua:
        browser = 'Safari'
    else:
        browser = 'Browser'
    if 'Android' in ua:
        device = 'Android'
    elif re.search(r'iPhone|iPad', ua):
        device = 'iOS'
    elif 'Mac OS' in ua:
        device = 'macOS'
    elif 'Windows' in ua:
        device = 'Windows'
    elif 'Linux' in ua:
        device = 'Linux'
    else:
        device = 'Unknown device'
    return device, browser


def _valid_ip(value):
    try:
        return str(ipaddress.ip_address((value or '').strip()))
    except ValueError:
        return None


def client_ip(request):
    # Proxy-aware (DJANGO_TRUSTED_PROXY_HOPS), so a client can't spoof it via X-Forwarded-For.
    return _valid_ip(request_client_ip(request))


def client_info(request):
    if request is None:
        return {'device': '', 'browser': '', 'user_agent': '', 'ip_address': None}
    user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:255]
    device, browser = parse_user_agent(user_agent)
    return {'device': device, 'browser': browser, 'user_agent': user_agent, 'ip_address': client_ip(request)}
