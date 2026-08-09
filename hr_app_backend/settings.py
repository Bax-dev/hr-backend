from pathlib import Path

from hr_app_backend.config import DATABASES, INSTALLED_APPS
from hr_app_backend.third_parties import build_django_cache_config
from hr_app_backend.utils import get_bool, get_env, get_int, get_list

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


DEBUG = get_bool("DJANGO_DEBUG", default=False)

# Signed tokens (employee invite links, password-reset links, session
# machinery) derive their HMAC key from SECRET_KEY, so a guessable value lets
# an attacker forge them. Reject known placeholders and short keys outright
# instead of silently falling back to one, even in DEBUG.
_WEAK_SECRET_KEYS = {
    "", "change-me", "changeme", "secret", "password",
    "django-insecure-development-key",
}
SECRET_KEY = get_env("DJANGO_SECRET_KEY", default="")
if SECRET_KEY.strip().lower() in _WEAK_SECRET_KEYS or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "DJANGO_SECRET_KEY is missing, a known placeholder, or shorter than 32 "
        "characters. Generate a real secret, e.g.:\n"
        "  python -c \"from django.core.management.utils import get_random_secret_key; "
        "print(get_random_secret_key())\""
    )

ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

# Number of trusted reverse proxies in front of Django that append to
# X-Forwarded-For (CloudFront + ALB by default). Used to pick the real client
# IP out of that header instead of trusting its attacker-controlled first hop.
TRUSTED_PROXY_HOPS = get_int("DJANGO_TRUSTED_PROXY_HOPS", default=2)

# The app sits behind CloudFront -> ALB; CloudFront terminates TLS to the
# browser but talks to the ALB over HTTP, so Django must be told the original
# request was HTTPS via this header, or request.is_secure() is always False
# and SECURE_SSL_REDIRECT would loop.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Only enforce HTTPS/HSTS and mark cookies Secure outside local dev, where
# the app is served over plain http://127.0.0.1.
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'hr_app_backend.middleware.DatabaseConnectionCleanupMiddleware',
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
FLUTTERWAVE_SECRET_KEY = get_env('FLUTTERWAVE_SECRET_KEY', '')
FLUTTERWAVE_PUBLIC_KEY = get_env('FLUTTERWAVE_PUBLIC_KEY', '')
FLUTTERWAVE_BASE_URL = get_env('FLUTTERWAVE_BASE_URL', 'https://api.flutterwave.com/v3')

CSRF_TRUSTED_ORIGINS = get_list('DJANGO_CSRF_TRUSTED_ORIGINS', default=[])

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
