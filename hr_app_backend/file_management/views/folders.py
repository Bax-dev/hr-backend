from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.serializers import parse_json_body
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError
from hr_app_backend.utils.idempotency import idempotent
from hr_app_backend.utils.pagination import paginated_data
from hr_app_backend.utils.throttles import throttle_view

from ..serializers import serialize_folder, serialize_folder_share
from ..services import (
    create_folder,
    create_folder_share,
    delete_folder,
    get_folder,
    list_folder_shares,
    list_folders,
    revoke_folder_share,
    update_folder,
)
from .helpers import require_user


@csrf_exempt
@require_http_methods(['GET', 'POST'])
@throttle_view('file_management:write', '120/min')
@idempotent('file_management:create-folder')
def folders_view(request):
    try:
        user = require_user(request)
        if request.method == 'GET':
            parent_id = request.GET.get('parent_id') or request.GET.get('parentId')
            search = request.GET.get('search')
            folders = list_folders(user, parent_id, search)
            return JsonResponse({
                'success': True,
                'data': paginated_data(
                    request,
                    folders,
                    lambda folder: serialize_folder(folder, user),
                    key='folders',
                ),
            })

        folder = create_folder(user, parse_json_body(request))
        return JsonResponse(serialize_folder(folder, user), status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def folder_detail_view(request, folder_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            folder = get_folder(user, folder_pk)
            return JsonResponse(serialize_folder(folder, user))

        if request.method == 'DELETE':
            delete_folder(user, folder_pk)
            return JsonResponse(None, safe=False, status=204)

        folder = update_folder(user, folder_pk, parse_json_body(request))
        return JsonResponse(serialize_folder(folder, user))
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
@throttle_view('file_management:write', '60/min')
def folder_shares_view(request, folder_pk):
    try:
        user = require_user(request)
        if request.method == 'GET':
            shares = list_folder_shares(user, folder_pk)
            return JsonResponse([serialize_folder_share(share) for share in shares], safe=False)

        share = create_folder_share(user, folder_pk, parse_json_body(request))
        return JsonResponse(serialize_folder_share(share), status=201)
    except AppError as exc:
        return error_response(exc)


@csrf_exempt
@require_http_methods(['DELETE'])
def folder_share_detail_view(request, folder_pk, share_pk):
    try:
        user = require_user(request)
        revoke_folder_share(user, folder_pk, share_pk)
        return JsonResponse(None, safe=False, status=204)
    except AppError as exc:
        return error_response(exc)
