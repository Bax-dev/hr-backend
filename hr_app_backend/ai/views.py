from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.employees.views.helpers import require_user
from hr_app_backend.utils.errors import AppError, ValidationError
from hr_app_backend.utils.throttles import throttle
from hr_app_backend.workspace_settings.services import is_copilot_enabled

from .service import ask_assistant


@csrf_exempt
@require_POST
def assistant_view(request):
    try:
        user = require_user(request)
        throttle(request, scope='ai-assistant', rate='20/min', ident=f'user:{user.pk}')
        organization = getattr(getattr(user, 'profile', None), 'organization', None)
        if not settings.AI_ASSISTANT_ENABLED or not is_copilot_enabled(organization):
            return JsonResponse(
                {'success': True, 'data': {'enabled': False, 'message': ''}}
            )

        payload = parse_json_body(request)
        messages = payload.get('messages')
        if not isinstance(messages, list) or not messages or len(messages) > 20:
            raise ValidationError('Send between 1 and 20 conversation messages.')
        if any(not isinstance(item, dict) for item in messages):
            raise ValidationError('Each conversation message must be an object.')
        if not any(item.get('role') == 'user' and str(item.get('content', '')).strip() for item in messages):
            raise ValidationError('A user message is required.')

        result = ask_assistant(
            messages=messages,
            page=str(payload.get('page', ''))[:200],
            user=user,
        )
        return JsonResponse({'success': True, 'data': {'enabled': True, **result}})
    except AppError as exc:
        return error_response(exc)
