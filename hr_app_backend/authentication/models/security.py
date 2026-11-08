"""Account-security records: signed-in sessions, sign-in history and two-step verification.

Secrets are never stored in plain text. Session tokens and MFA challenge tokens are stored
as sha256 digests, recovery codes as keyed HMACs, and the authenticator (TOTP) secret is
Fernet-encrypted (see ``authentication.services.mfa``).
"""

from django.conf import settings
from django.db import models

from hr_app_backend.utils.ids import UUIDPrimaryKeyModel


class UserSession(UUIDPrimaryKeyModel):
    """One signed-in device. The bearer token itself is only held by the client."""

    REVOKED_LOGOUT = 'logout'
    REVOKED_BY_USER = 'revoked'
    REVOKED_OTHERS = 'revoke_others'
    REVOKED_PASSWORD_CHANGED = 'password_changed'
    REVOKED_PASSWORD_RESET = 'password_reset'
    REVOKED_MFA_DISABLED = 'mfa_disabled'
    REVOKED_DISABLED = 'disabled'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='auth_sessions')
    token_hash = models.CharField(max_length=64, unique=True)
    device = models.CharField(max_length=40, blank=True)
    browser = models.CharField(max_length=40, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=32, blank=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'revoked_at'])]

    def __str__(self):
        return f'{self.user_id} {self.device}/{self.browser}'


class LoginEvent(UUIDPrimaryKeyModel):
    """Sign-in history. ``reason`` is set for failures and also drives the lockout counter."""

    REASON_WRONG_PASSWORD = 'Wrong password'
    REASON_WRONG_MFA = 'Wrong verification code'
    REASON_LOCKED = 'Locked out'
    REASON_DISABLED = 'Account disabled'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='login_events')
    created_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    reason = models.CharField(max_length=40, blank=True)
    device = models.CharField(max_length=40, blank=True)
    browser = models.CharField(max_length=40, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]


class MfaDevice(models.Model):
    """The user's authenticator app (TOTP, RFC 6238). Active once ``confirmed_at`` is set."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name='mfa_device'
    )
    secret_encrypted = models.TextField()  # never returned after setup
    confirmed_at = models.DateTimeField(null=True, blank=True)
    # Highest TOTP time-step accepted so far, so a code can't be replayed within its window.
    last_used_counter = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def enabled(self):
        return self.confirmed_at is not None


class MfaRecoveryCode(UUIDPrimaryKeyModel):
    """Single-use backup codes for when the authenticator is lost."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mfa_recovery_codes')
    code_hash = models.CharField(max_length=64, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MfaChallenge(UUIDPrimaryKeyModel):
    """Second sign-in step: issued after a correct password, exchanged for a session with a valid code."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mfa_challenges')
    token_hash = models.CharField(max_length=64, unique=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
