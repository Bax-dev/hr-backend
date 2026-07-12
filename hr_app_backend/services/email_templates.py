from django.template.loader import render_to_string

from hr_app_backend.utils import local_now


DEFAULT_EMAIL_CONTEXT = {
    'brand_name': 'Workiva',
    'product_name': 'Workiva HR',
    'support_email': 'support@workiva.com.ng',
}


def render_email_template(template_name, context=None):
    payload = {
        **DEFAULT_EMAIL_CONTEXT,
        'current_year': local_now().year,
        **(context or {}),
    }
    return render_to_string(template_name, payload)
