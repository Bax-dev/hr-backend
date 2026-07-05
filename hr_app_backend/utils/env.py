import os


def get_env(name, default=None):
    return os.getenv(name, default)


def get_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int(name, default=0):
    value = os.getenv(name)
    if value is None:
        return default

    return int(value)


def get_list(name, default=None, separator=","):
    value = os.getenv(name)
    if value is None:
        return default[:] if isinstance(default, list) else (default or [])

    return [item.strip() for item in value.split(separator) if item.strip()]
