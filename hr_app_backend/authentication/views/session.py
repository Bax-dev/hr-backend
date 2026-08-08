from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from datetime import date

from hr_app_backend.utils.errors import AppError, AuthenticationError, PermissionDeniedError, ValidationError
from hr_app_backend.utils.throttles import throttle, throttle_view

from ..serializers import serialize_user
from ..serializers import change_password_payload, login_payload
from ..services import auth_response, change_password, destroy_session, get_user_by_token, login_user
from .helpers import error_response, load_json, token_from_request


@csrf_exempt
@require_POST
@throttle_view('auth:login:ip', '20/min')
def login_view(request):
    try:
        payload = login_payload(load_json(request))
        # The per-IP limit above does not stop credential stuffing spread across
        # many IPs, so also cap attempts against a single account.
        throttle(request, scope='auth:login:account', rate='10/min', ident=payload['email'].lower())
        user = login_user(payload)
        return JsonResponse({'success': True, 'data': auth_response(user)})
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH'])
def me_view(request):
    token = token_from_request(request)
    user = get_user_by_token(token)
    if user is None:
        return error_response(AuthenticationError('Authentication credentials were not provided or are invalid.'))
    if request.method == 'PATCH':
        try:
            profile = user.profile
            if profile.account_type != profile.ACCOUNT_TYPE_INDIVIDUAL or profile.organization_id:
                raise PermissionDeniedError('This endpoint only updates standalone personal accounts.')
            payload = load_json(request)
            first_name = str(payload.get('first_name', user.first_name)).strip()
            last_name = str(payload.get('last_name', user.last_name)).strip()
            phone = str(payload.get('phone', profile.phone)).strip()
            gender = str(payload.get('gender', profile.gender)).strip()
            country = str(payload.get('country', profile.country)).strip()
            birthday = str(payload.get('date_of_birth', profile.date_of_birth or '')).strip()
            if not first_name or not last_name:
                raise ValidationError('First name and last name are required.')
            if gender and gender not in dict(profile.GENDER_CHOICES):
                raise ValidationError('Gender must be male, female, or prefer_not_to_say.')
            parsed_birthday = date.fromisoformat(birthday) if birthday else None
            if parsed_birthday and parsed_birthday > date.today():
                raise ValidationError('Birthday cannot be in the future.')
            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=['first_name', 'last_name'])
            profile.full_name = f'{first_name} {last_name}'.strip()
            profile.phone = phone
            profile.gender = gender
            profile.country = country
            profile.date_of_birth = parsed_birthday
            profile.save(update_fields=['full_name', 'phone', 'gender', 'country', 'date_of_birth', 'updated_at'])
        except (AppError, ValueError) as exc:
            if isinstance(exc, AppError):
                return error_response(exc)
            return JsonResponse({'success': False, 'message': 'Birthday must be a valid date.'}, status=400)
    return JsonResponse({'success': True, 'data': {'user': serialize_user(user)}})


@csrf_exempt
@require_POST
def logout_view(request):
    destroy_session(token_from_request(request))
    return JsonResponse({'success': True, 'message': 'Logged out successfully.'})


@csrf_exempt
@require_POST
@throttle_view('auth:change-password', '10/min')
def change_password_view(request):
    try:
        token = token_from_request(request)
        user = get_user_by_token(token)
        if user is None:
            raise AuthenticationError('Authentication credentials were not provided or are invalid.')
        updated_user = change_password(user, change_password_payload(load_json(request)))
        return JsonResponse({'success': True, 'data': {'user': serialize_user(updated_user)}})
    except AppError as exc:
        return error_response(exc)
