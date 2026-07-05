import json

from django.http import JsonResponse

from hr_app_backend.utils.errors import AppError


def load_json(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError as exc:
        raise AppError('Request body must be valid JSON.') from exc


def token_from_request(request):
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header.removeprefix('Bearer ').strip()
    return ''


def error_response(error):
    return JsonResponse({'success': False, 'message': error.message}, status=error.status_code)
