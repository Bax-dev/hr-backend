from django.utils import timezone


def local_now():
    return timezone.localtime(timezone.now())


def today_local():
    return local_now().date()
