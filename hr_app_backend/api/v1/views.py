import hashlib
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.services import get_user_by_token
from hr_app_backend.authentication.views.helpers import error_response, token_from_request
from hr_app_backend.utils.env import get_env
from hr_app_backend.utils.errors import AppError, AuthenticationError, ValidationError


def health_check(_request):
    return JsonResponse({"status": "ok", "version": "v1"})


def _require_user(request):
    user = get_user_by_token(token_from_request(request))
    if user is None:
        raise AuthenticationError('Authentication credentials were not provided or are invalid.')
    return user


def _build_cloudinary_signature(*, folder: str, public_id: str, timestamp: int, api_secret: str) -> str:
    parts = []
    if folder:
        parts.append(f'folder={folder}')
    parts.append(f'public_id={public_id}')
    parts.append(f'timestamp={timestamp}')
    payload = '&'.join(parts) + api_secret
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()


def _public_url(*, cloud_name: str, resource_type: str, key: str) -> str:
    return f'https://res.cloudinary.com/{cloud_name}/{resource_type}/upload/{quote(key, safe="/")}'


@csrf_exempt
@require_http_methods(['POST'])
def upload_presign_view(request):
    try:
        _require_user(request)
        payload = parse_json_body(request)

        filename = str(payload.get('filename') or '').strip()
        content_type = str(payload.get('content_type') or payload.get('contentType') or '').strip()
        folder = str(payload.get('folder') or '').strip().strip('/')

        if not filename:
            raise ValidationError('Filename is required.')
        if not content_type:
            raise ValidationError('Content type is required.')

        cloud_name = get_env('CLOUDINARY_CLOUD_NAME', '')
        api_key = get_env('CLOUDINARY_API_KEY', '')
        api_secret = get_env('CLOUDINARY_API_SECRET', '')
        if not cloud_name or not api_key or not api_secret:
            raise AppError('Cloudinary upload is not configured on the server.', status_code=500)

        resource_type = 'image' if content_type.startswith('image/') else 'raw'
        suffix = Path(filename).suffix.lower()
        public_id = uuid4().hex if resource_type == 'image' else f"{uuid4().hex}{suffix}"
        timestamp = int(time.time())
        signature = _build_cloudinary_signature(
            folder=folder,
            public_id=public_id,
            timestamp=timestamp,
            api_secret=api_secret,
        )

        key = f'{folder}/{public_id}' if folder else public_id
        fields = {
            'api_key': api_key,
            'timestamp': str(timestamp),
            'signature': signature,
            'public_id': public_id,
        }
        if folder:
            fields['folder'] = folder

        return JsonResponse({
            'method': 'POST',
            'url': f'https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload',
            'fields': fields,
            'key': key,
            'public_url': _public_url(cloud_name=cloud_name, resource_type=resource_type, key=key),
        })
    except AppError as exc:
        return error_response(exc)
