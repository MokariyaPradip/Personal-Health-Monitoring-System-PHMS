from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

try:
    from flask import has_app_context, current_app
except ImportError:  # pragma: no cover - Flask is always available in the app runtime.
    has_app_context = lambda: False  # type: ignore
    current_app = None  # type: ignore


_TOKEN_PREFIX = 'v1:'


def _get_secret_key() -> str:
    if has_app_context() and current_app is not None:
        secret_key = current_app.config.get('SECRET_KEY')
        if secret_key:
            return str(secret_key)

    secret_key = os.getenv('SECRET_KEY')
    if secret_key:
        return secret_key

    raise RuntimeError('SECRET_KEY is required to encrypt smartwatch tokens')


def _get_fernet() -> Fernet:
    secret_key = _get_secret_key().encode('utf-8')
    derived_key = hashlib.sha256(secret_key).digest()
    fernet_key = base64.urlsafe_b64encode(derived_key)
    return Fernet(fernet_key)


def encrypt_token_value(value: str | None) -> str | None:
    if value is None:
        return None
    if value.startswith(_TOKEN_PREFIX):
        return value

    token = _get_fernet().encrypt(value.encode('utf-8')).decode('utf-8')
    return f'{_TOKEN_PREFIX}{token}'


def decrypt_token_value(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith(_TOKEN_PREFIX):
        return value

    encrypted_value = value[len(_TOKEN_PREFIX):]
    try:
        return _get_fernet().decrypt(encrypted_value.encode('utf-8')).decode('utf-8')
    except InvalidToken as exc:
        raise ValueError('Unable to decrypt smartwatch token value') from exc
