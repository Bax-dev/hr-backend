from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from hr_app_backend.authentication.models import UserProfile
from hr_app_backend.authentication.views.helpers import error_response
from hr_app_backend.utils.errors import AppError, ValidationError
from hr_app_backend.utils.pagination import paginated_data

from .helpers import require_superuser

ROLE_EMPLOYEE = 'employee'
ROLE_COMPANY_ADMIN = 'company_admin'
ROLES = {ROLE_EMPLOYEE, ROLE_COMPANY_ADMIN}


def _role_for(profile):
    if profile.account_type == UserProfile.ACCOUNT_TYPE_COMPANY and not profile.employee_id:
        return ROLE_COMPANY_ADMIN
    return ROLE_EMPLOYEE


def _serialize_user(profile):
    return {
        'id': profile.user_id,
        'email': profile.user.email,
        'fullName': profile.full_name,
        'phone': profile.phone,
        'role': _role_for(profile),
        'accountType': profile.account_type,
        'organization': {
            'id': str(profile.organization_id), 'name': profile.organization.name,
        } if profile.organization_id else None,
        'isSuperuser': profile.user.is_superuser,
        'emailVerified': profile.email_verified,
        'createdAt': profile.created_at.isoformat(),
    }


@require_GET
def user_list_view(request):
    try:
        require_superuser(request)
        profiles = UserProfile.objects.select_related('user', 'organization', 'employee').order_by('-created_at')

        role = request.GET.get('role', '').strip()
        if role and role != 'all':
            if role not in ROLES:
                raise ValidationError('role must be one of all, employee, company_admin.')
            if role == ROLE_COMPANY_ADMIN:
                profiles = profiles.filter(account_type=UserProfile.ACCOUNT_TYPE_COMPANY, employee__isnull=True)
            else:
                profiles = profiles.exclude(account_type=UserProfile.ACCOUNT_TYPE_COMPANY, employee__isnull=True)

        organization_id = request.GET.get('organization_id', '').strip()
        if organization_id:
            profiles = profiles.filter(organization_id=organization_id)

        search = request.GET.get('search', '').strip()
        if search:
            profiles = profiles.filter(Q(user__email__icontains=search) | Q(full_name__icontains=search))

        data = paginated_data(request, profiles, _serialize_user, key='users', default_page_size=25)
        return JsonResponse({'success': True, 'data': data})
    except AppError as exc:
        return error_response(exc)
