from hr_app_backend.utils import get_env, get_int


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
