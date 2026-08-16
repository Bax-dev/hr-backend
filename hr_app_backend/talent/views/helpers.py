from django.http import JsonResponse

from hr_app_backend.utils.pagination import paginated_data


def collection_response(request, key, records, serializer):
    return JsonResponse({'success': True, 'data': paginated_data(request, records, serializer, key=key)})


def detail_response(key, record, serializer, status=200):
    return JsonResponse({'success': True, 'data': {key: serializer(record)}}, status=status)
