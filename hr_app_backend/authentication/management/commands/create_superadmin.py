from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from hr_app_backend.utils import get_env

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Idempotently bootstraps a Django /admin/ superuser from the '
        'SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD environment variables. '
        'A no-op if either is unset. Safe to run on every deploy: it never '
        "overwrites an existing user's password unless --reset-password is given."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help="Also reset the existing superadmin's password to SUPERADMIN_PASSWORD.",
        )

    def handle(self, *args, **options):
        email = get_env('SUPERADMIN_EMAIL', default='').strip().lower()
        password = get_env('SUPERADMIN_PASSWORD', default='')

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                'SUPERADMIN_EMAIL/SUPERADMIN_PASSWORD not set — skipping superadmin bootstrap.'
            ))
            return

        try:
            validate_email(email)
        except DjangoValidationError as exc:
            raise CommandError(f'SUPERADMIN_EMAIL is not a valid email address: {"; ".join(exc.messages)}') from exc

        user = User.objects.filter(email__iexact=email).first()

        if user is None:
            self._validate_password(password)
            User.objects.create_superuser(username=email, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Created superadmin {email}.'))
            return

        changed = False
        
        if user.username != email:
            if User.objects.filter(username__iexact=email).exclude(pk=user.pk).exists():
                raise CommandError(
                    f'Cannot set the superadmin username to {email}: that username is already in use.'
                )
            user.username = email
            changed = True

        for flag in ('is_staff', 'is_superuser', 'is_active'):
            if not getattr(user, flag):
                setattr(user, flag, True)
                changed = True

        if options['reset_password']:
            self._validate_password(password, user=user)
            user.set_password(password)
            changed = True

        if changed:
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Updated superadmin {email}.'))
        else:
            self.stdout.write(f'Superadmin {email} already up to date.')

    def _validate_password(self, password, user=None):
        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            raise CommandError(f'SUPERADMIN_PASSWORD is too weak: {"; ".join(exc.messages)}') from exc
