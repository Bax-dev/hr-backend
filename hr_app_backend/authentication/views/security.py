"""Account security endpoints: signed-in devices, sign-in history and two-step verification."""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from hr_app_backend.utils.errors import AppError, AuthenticationError, NotFoundError, ValidationError
from hr_app_backend.utils.throttles import throttle, throttle_view

from ..models import UserSession
from ..services import (
    active_sessions,
    current_session_id,
    get_user_by_token,
    login_history,
    revoke_all_sessions,
    revoke_session,
    serialize_session,
)
from ..services import mfa
from .helpers import error_response, load_json, session_json_response, token_from_request
from .session import record_sign_in


def _require_user(request):
    user = get_user_by_token(token_from_request(request))
    if user is None:
        raise AuthenticationError('Authentication credentials were not provided or are invalid.')
    return user


def _value(payload, *keys):
    for key in keys:
        value = payload.get(key)
        if value not in (None, ''):
            return str(value).strip()
    return ''


# ---------------------------------------------------------------- sessions


@csrf_exempt
@require_GET
def sessions_view(request):
    try:
        user = _require_user(request)
        current_id = current_session_id(user)
        sessions = active_sessions(user).order_by('-last_active_at')
        return JsonResponse(
            {'success': True, 'data': {'sessions': [serialize_session(s, current_id) for s in sessions]}}
        )
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['DELETE'])
def session_detail_view(request, session_id):
    try:
        user = _require_user(request)
        if not revoke_session(user, session_id):
            raise NotFoundError('Session not found.')
        return JsonResponse({'success': True, 'message': 'Session signed out.'})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
def revoke_other_sessions_view(request):
    try:
        user = _require_user(request)
        revoked = revoke_all_sessions(user, UserSession.REVOKED_OTHERS, except_session_id=current_session_id(user))
        return JsonResponse({'success': True, 'data': {'sessions_revoked': revoked}})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_GET
def login_history_view(request):
    try:
        user = _require_user(request)
        return JsonResponse({'success': True, 'data': {'events': login_history(user)}})
    except AppError as exc:
        return error_response(exc)


# ---------------------------------------------------------------- two-step verification


@csrf_exempt
@require_GET
def mfa_status_view(request):
    try:
        user = _require_user(request)
        return JsonResponse({'success': True, 'data': mfa.status_for(user)})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:mfa:manage', '10/min')
def mfa_setup_view(request):
    try:
        user = _require_user(request)
        payload = load_json(request)
        return JsonResponse({'success': True, 'data': mfa.begin_setup(user, payload.get('password'))})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:mfa:manage', '10/min')
def mfa_enable_view(request):
    try:
        user = _require_user(request)
        code = _value(load_json(request), 'code')
        if not code:
            raise ValidationError('Enter the code from your authenticator app.')
        return JsonResponse({'success': True, 'data': mfa.enable(request, user, code)})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:mfa:manage', '10/min')
def mfa_disable_view(request):
    try:
        user = _require_user(request)
        payload = load_json(request)
        code = _value(payload, 'code', 'recovery_code', 'recoveryCode')
        if not code:
            raise ValidationError('Enter a code from your authenticator app or a recovery code.')
        return JsonResponse({'success': True, 'data': mfa.disable(request, user, payload.get('password'), code)})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:mfa:manage', '10/min')
def mfa_recovery_codes_view(request):
    try:
        user = _require_user(request)
        payload = load_json(request)
        code = _value(payload, 'code', 'recovery_code', 'recoveryCode')
        if not code:
            raise ValidationError('Enter a code from your authenticator app or a recovery code.')
        result = mfa.regenerate_recovery_codes(request, user, payload.get('password'), code)
        return JsonResponse({'success': True, 'data': result})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_POST
@throttle_view('auth:mfa:verify:ip', '20/min')
def mfa_verify_view(request):
    try:
        payload = load_json(request)
        token = _value(payload, 'mfa_token', 'mfaToken')
        if not token:
            raise ValidationError('Sign in again.', code='MFA_CHALLENGE_INVALID')
        # Per-challenge limit on top of the challenge's own 5-attempt cap.
        throttle(request, scope='auth:mfa:verify:token', rate='10/min', ident=token[:64])
        user, result = mfa.verify_challenge(
            request,
            token,
            code=_value(payload, 'code'),
            recovery_code=_value(payload, 'recovery_code', 'recoveryCode'),
        )
        record_sign_in(request, user)
        # Token goes into the httpOnly session cookie, never the JSON body.
        return session_json_response(result)
    except AppError as exc:
        return error_response(exc)
