from django.http import JsonResponse


def collection_response(key, records, serializer):
    return JsonResponse({'success': True, 'data': {key: [serializer(record) for record in records]}})


def detail_response(key, record, serializer, status=200):
    return JsonResponse({'success': True, 'data': {key: serializer(record)}}, status=status)
