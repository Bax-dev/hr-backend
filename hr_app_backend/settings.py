from pathlib import Path

from hr_app_backend.third_parties import build_django_cache_config
from hr_app_backend.utils import get_bool, get_env, get_int, get_list

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


DEBUG = get_bool("DJANGO_DEBUG", default=False)
SECRET_KEY = get_env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "django-insecure-development-key"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is disabled.")

ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'hr_app_backend.middleware.RequestIDMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'hr_app_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'hr_app_backend.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': get_env('DB_NAME', 'hr_app_db'),
        'USER': get_env('DB_USER', 'postgres'),
        'PASSWORD': get_env('DB_PASSWORD', ''),
        'HOST': get_env('DB_HOST', '127.0.0.1'),
        'PORT': get_int('DB_PORT', 5432),
        'CONN_MAX_AGE': get_int('DB_CONN_MAX_AGE', 60),
        'OPTIONS': {
            'sslmode': get_env('DB_SSLMODE', 'prefer'),
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = get_env('DJANGO_LANGUAGE_CODE', 'en-us')

TIME_ZONE = get_env('DJANGO_TIME_ZONE', 'UTC')

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

CACHES = {
    'default': build_django_cache_config(),
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

EMAIL_BACKEND = get_env('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = get_env('DJANGO_EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = get_int('DJANGO_EMAIL_PORT', 587)
EMAIL_HOST_USER = get_env('DJANGO_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = get_env('DJANGO_EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = get_bool('DJANGO_EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = get_bool('DJANGO_EMAIL_USE_SSL', default=False)
DEFAULT_FROM_EMAIL = get_env('DJANGO_DEFAULT_FROM_EMAIL', 'noreply@hrapp.local')

PAYSTACK_SECRET_KEY = get_env('PAYSTACK_SECRET_KEY', '')
PAYSTACK_PUBLIC_KEY = get_env('PAYSTACK_PUBLIC_KEY', '')
PAYSTACK_BASE_URL = get_env('PAYSTACK_BASE_URL', 'https://api.paystack.co')

CSRF_TRUSTED_ORIGINS = get_list('DJANGO_CSRF_TRUSTED_ORIGINS', default=[])

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
