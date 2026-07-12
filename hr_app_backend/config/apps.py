DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = []

LOCAL_APPS = [
    'hr_app_backend.attendance',
    'hr_app_backend.authentication',
    'hr_app_backend.billing',
    'hr_app_backend.departments',
    'hr_app_backend.employees',
    'hr_app_backend.leave',
    'hr_app_backend.platform',
    'hr_app_backend.talent',
    'hr_app_backend.workspace_settings',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
