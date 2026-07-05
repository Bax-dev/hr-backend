from django.http import JsonResponse


def health_check(_request):
    return JsonResponse({"status": "ok", "version": "v1"})
