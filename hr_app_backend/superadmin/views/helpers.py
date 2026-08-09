from hr_app_backend.employees.views.helpers import require_user
from hr_app_backend.utils.errors import PermissionDeniedError


def require_superuser(request):
    user = require_user(request)
    if not user.is_superuser:
        raise PermissionDeniedError('Only platform superadmins can access this.')
    return user
