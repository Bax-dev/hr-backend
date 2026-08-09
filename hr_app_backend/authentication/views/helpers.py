import json
from http import HTTPStatus

from django.conf import settings
from django.http import JsonResponse

from hr_app_backend.utils.errors import AppError

# Session token lives in an httpOnly cookie so it can't be read by JavaScript
# (mitigates XSS-driven token theft). The Authorization header fallback below
# exists only for non-browser API clients (scripts, Postman, etc).
SESSION_COOKIE_NAME = 'session_token'
SESSION_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # keep in sync with sessions.SESSION_EXPIRY_SECONDS


def load_json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError as exc:
        raise AppError('Request body must be valid JSON.') from exc


def token_from_request(request):
    cookie_token = request.COOKIES.get(SESSION_COOKIE_NAME, '')
    if cookie_token:
        return cookie_token
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header.removeprefix('Bearer ').strip()
    return ''


def set_session_cookie(response, token):
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        secure=not settings.DEBUG,
        samesite='Lax',
        path='/',
    )


def clear_session_cookie(response):
    response.delete_cookie(SESSION_COOKIE_NAME, path='/')


def session_json_response(session_payload, status=200):
    """Build a JsonResponse for an auth_response()-style {'token', 'user'}
    payload: the token goes into the httpOnly cookie, never the JSON body."""
    data = dict(session_payload)
    token = data.pop('token', None)
    response = JsonResponse({'success': True, 'data': data}, status=status)
    if token:
        set_session_cookie(response, token)
    return response


def error_response(error):
    status = int(getattr(error, 'status_code', 400) or 400)
    try:
        status_title = HTTPStatus(status).phrase
    except ValueError:
        status_title = 'Request Error'

    detail = str(getattr(error, 'message', '') or 'Something went wrong. Please try again.').strip()

    return JsonResponse(
        {
            'success': False,
            'statusCode': status,
            'status': status_title,
            'message': detail,
            'detail': detail,
            'error': status_title.lower().replace(' ', '_'),
        },
        status=status,
    )
