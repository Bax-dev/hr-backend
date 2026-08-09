from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.services import get_user_by_token, validate_employee_invite
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


def _s3_client():
    region = get_env('AWS_REGION', 'us-east-1').strip()
    endpoint_url = get_env('AWS_S3_ENDPOINT_URL', '').strip() or None
    return boto3.client(
        's3',
        region_name=region,
        endpoint_url=endpoint_url,
        config=Config(signature_version='s3v4'),
    )


def _storage_bucket():
    bucket = get_env('AWS_STORAGE_BUCKET_NAME', '').strip()
    if not bucket:
        raise AppError('S3 upload is not configured on the server.', status_code=500)
    return bucket


def _safe_folder(value):
    parts = [part for part in value.strip().strip('/').split('/') if part]
    if any(part in {'.', '..'} for part in parts):
        raise ValidationError('Upload folder is invalid.')
    return '/'.join(parts)


@csrf_exempt
@require_http_methods(['POST'])
def upload_presign_view(request):
    try:
        payload = parse_json_body(request)
        invite_token = str(payload.get('invite_token') or '').strip()
        if invite_token:
            validate_employee_invite(invite_token)
        else:
            _require_user(request)

        filename = str(payload.get('filename') or '').strip()
        content_type = str(payload.get('content_type') or payload.get('contentType') or '').strip()
        file_size = payload.get('file_size', payload.get('fileSize'))
        folder = _safe_folder(str(payload.get('folder') or ''))
        if invite_token and folder != 'employee-avatars':
            raise ValidationError('Employee invitations may only upload profile pictures.')

        if not filename:
            raise ValidationError('Filename is required.')
        if not content_type:
            raise ValidationError('Content type is required.')
        if content_type.startswith('image/'):
            allowed_image_types = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
            if content_type not in allowed_image_types:
                raise ValidationError('Unsupported image type. Use PNG, JPG, WEBP, or GIF.')
            try:
                image_size = int(file_size)
            except (TypeError, ValueError) as exc:
                raise ValidationError('Image file size is required.') from exc
            if image_size <= 0:
                raise ValidationError('Image file size must be greater than zero.')
            if image_size > 5 * 1024 * 1024:
                raise ValidationError('Image must not exceed 5 MB.')
        else:
            try:
                document_size = int(file_size)
            except (TypeError, ValueError) as exc:
                raise ValidationError('Document file size is required.') from exc
            if document_size <= 0:
                raise ValidationError('Document file size must be greater than zero.')
            if document_size > 10 * 1024 * 1024:
                raise ValidationError('Document must not exceed 10 MB.')

        bucket = _storage_bucket()
        suffix = Path(filename).suffix.lower()
        object_name = f'{uuid4().hex}{suffix}'
        key = f'{folder}/{object_name}' if folder else object_name
        client = _s3_client()
        url = client.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket, 'Key': key, 'ContentType': content_type},
            ExpiresIn=900,
        )

        return JsonResponse({
            'method': 'PUT',
            'url': url,
            'headers': {'Content-Type': content_type},
            'key': key,
            'public_url': request.build_absolute_uri(f'/api/v1/uploads/files/{quote(key, safe="/")}/'),
        })
    except (BotoCoreError, ClientError):
        return error_response(AppError('Could not create the S3 upload URL.', status_code=502))
    except AppError as exc:
        return error_response(exc)


@require_http_methods(['GET'])
def upload_file_view(_request, key):
    try:
        safe_key = _safe_folder(key)
        if not safe_key or safe_key != key.strip('/'):
            raise ValidationError('File key is invalid.')
        url = _s3_client().generate_presigned_url(
            'get_object',
            Params={'Bucket': _storage_bucket(), 'Key': safe_key},
            ExpiresIn=300,
        )
        return redirect(url)
    except (BotoCoreError, ClientError):
        return error_response(AppError('Could not retrieve the S3 file.', status_code=502))
    except AppError as exc:
        return error_response(exc)
