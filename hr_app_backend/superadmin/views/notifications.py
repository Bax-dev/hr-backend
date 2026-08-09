from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from hr_app_backend.authentication.models import Organization
from hr_app_backend.authentication.views.helpers import error_response, load_json
from hr_app_backend.platform.bulk_notifications import enqueue_bulk_notification
from hr_app_backend.platform.models import BulkNotification
from hr_app_backend.utils.errors import AppError, NotFoundError, ValidationError
from hr_app_backend.utils.pagination import paginated_data

from .helpers import require_superuser


def _serialize_campaign(campaign):
    return {
        'id': str(campaign.id),
        'organization': {
            'id': str(campaign.organization_id), 'name': campaign.organization.name,
        } if campaign.organization_id else None,
        'title': campaign.title,
        'body': campaign.body,
        'status': campaign.status,
        'recipientCount': campaign.recipient_count,
        'sentCount': campaign.sent_count,
        'failedCount': campaign.failed_count,
        'createdBy': campaign.created_by.email if campaign.created_by_id else None,
        'createdAt': campaign.created_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def campaign_list_view(request):
    try:
        user = require_superuser(request)

        if request.method == 'POST':
            payload = load_json(request)
            organization_id = str(payload.get('organization_id', '')).strip()
            title = str(payload.get('title', '')).strip()
            body = str(payload.get('body', '')).strip()
            if not organization_id:
                raise ValidationError('organization_id is required.')
            if not title or not body:
                raise ValidationError('title and body are required.')
            organization = Organization.objects.filter(id=organization_id).first()
            if organization is None:
                raise NotFoundError('Company not found.')

            campaign = enqueue_bulk_notification(
                organization=organization, created_by=user, title=title, body=body,
            )
            return JsonResponse({'success': True, 'data': {'campaign': _serialize_campaign(campaign)}}, status=201)

        campaigns = BulkNotification.objects.select_related('organization', 'created_by')
        organization_id = request.GET.get('organization_id', '').strip()
        if organization_id:
            campaigns = campaigns.filter(organization_id=organization_id)

        data = paginated_data(request, campaigns, _serialize_campaign, key='campaigns', default_page_size=25)
        return JsonResponse({'success': True, 'data': data})
    except AppError as exc:
        return error_response(exc)
