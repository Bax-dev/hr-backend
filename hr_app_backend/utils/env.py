from decouple import Csv, config


def get_env(name, default=None):
    return config(name, default=default)


def get_bool(name, default=False):
    return config(name, default=default, cast=bool)


def get_int(name, default=0):
    return config(name, default=default, cast=int)


def get_list(name, default=None, separator=","):
    fallback = default[:] if isinstance(default, list) else (default or [])
    value = config(name, default=None)
    if value is None:
        return fallback

    return config(name, cast=Csv(delimiter=separator))
