from django.template.loader import render_to_string

from hr_app_backend.utils import get_env, local_now


DEFAULT_LOGO_URL = 'https://workiva.com.ng/transparent-logo-mark.png'

DEFAULT_EMAIL_CONTEXT = {
    'brand_name': 'Workiva',
    'product_name': 'Workiva HR',
    'support_email': 'support@workiva.com.ng',
}


def render_email_template(template_name, context=None):
    payload = {
        **DEFAULT_EMAIL_CONTEXT,
        'logo_url': get_env('EMAIL_LOGO_URL', DEFAULT_LOGO_URL).strip() or DEFAULT_LOGO_URL,
        'current_year': local_now().year,
        **(context or {}),
    }
    return render_to_string(template_name, payload)
