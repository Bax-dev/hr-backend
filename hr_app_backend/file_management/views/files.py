from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.idempotency import idempotent
from hr_app_backend.utils.throttles import throttle_view

from ..serializers import serialize_file, serialize_share
from ..services import (
    create_share,
    delete_file,
    get_file,
    list_files,
    list_shares,
    presign_upload,
    register_file,
    resolve_download_url,
    resolve_public_download_url,
    revoke_share,
    update_file,
)
from .helpers import require_user


@csrf_exempt
@require_http_methods(['POST'])
@throttle_view('file_management:write', '60/min')
def files_presign_view(request):
    try:
        user = require_user(request)
        result = presign_upload(user, parse_json_body(request))
        return JsonResponse({
            'method': result['method'],
            'url': result['url'],
            'headers': result['headers'],
            'key': result['key'],
            'bucket': result['bucket'],
        })
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
@throttle_view('file_management:write', '120/min')
@idempotent('file_management:register-file')
def files_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            folder_id = request.GET.get('folder_id') or request.GET.get('folderId')
            search = request.GET.get('search')
            files = list_files(user, folder_id, search)
            return JsonResponse([serialize_file(f, user) for f in files], safe=False)

        file_asset = register_file(user, parse_json_body(request), request=request)
        return JsonResponse(serialize_file(file_asset, user), status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def file_detail_view(request, file_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            file_asset = get_file(user, file_pk)
            return JsonResponse(serialize_file(file_asset, user))

        if request.method == 'DELETE':
            delete_file(user, file_pk, request=request)
            return JsonResponse(None, safe=False, status=204)

        file_asset = update_file(user, file_pk, parse_json_body(request), request=request)
        return JsonResponse(serialize_file(file_asset, user))
    except AppError as exc:
        return error_response(exc)


def _disposition_from_request(request):
    return 'inline' if request.GET.get('disposition') == 'inline' else 'attachment'


@require_http_methods(['GET'])
def file_download_view(request, file_pk):
    try:
        user = require_user(request)
        url = resolve_download_url(user, file_pk, disposition=_disposition_from_request(request))
        return redirect(url)
    except AppError as exc:
        return error_response(exc)


@require_http_methods(['GET'])
def file_public_download_view(request, file_pk):
    try:
        url = resolve_public_download_url(file_pk, disposition=_disposition_from_request(request))
        return redirect(url)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
@throttle_view('file_management:write', '60/min')
def file_shares_view(request, file_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            shares = list_shares(user, file_pk)
            return JsonResponse([serialize_share(share) for share in shares], safe=False)

        share = create_share(user, file_pk, parse_json_body(request), request=request)
        return JsonResponse(serialize_share(share), status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['DELETE'])
def file_share_detail_view(request, file_pk, share_pk):
    try:
        user = require_user(request)
        revoke_share(user, file_pk, share_pk, request=request)
        return JsonResponse(None, safe=False, status=204)
    except AppError as exc:
        return error_response(exc)
