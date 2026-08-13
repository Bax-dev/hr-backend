import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

from hr_app_backend.utils.errors import AppError


@lru_cache(maxsize=1)
def _fernet():
    key = getattr(settings, 'FILE_STORAGE_ENCRYPTION_KEY', '') or ''
    if len(key) < 32:
        raise AppError(
            'File storage encryption is not configured on the server.', status_code=500
        )
    # Accept any sufficiently long secret rather than requiring an operator to
    # hand-generate a base64 Fernet key: derive one deterministically so the
    # same env var value always decrypts what it encrypted.
    derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode('utf-8')).digest())
    return Fernet(derived)


def encrypt_secret(plaintext):
    if not plaintext:
        return ''
    return _fernet().encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt_secret(ciphertext):
    if not ciphertext:
        return ''
    try:
        return _fernet().decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except InvalidToken as exc:
        raise AppError('Stored S3 credentials could not be decrypted.', status_code=500) from exc
