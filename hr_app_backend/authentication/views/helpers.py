import json
from http import HTTPStatus

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
