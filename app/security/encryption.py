# app\security\encryption.py

"""Field-level encryption for sensitive personal data (ФЗ-152 ст.19 «сохранность ПДн»).

Uses Fernet (AES-128-CBC + HMAC) via ``cryptography``. ``MultiFernet`` provides
key rotation: the first key encrypts new values, any listed key can decrypt.

Two SQLAlchemy ``TypeDecorator``s — ``EncryptedText`` and ``EncryptedJSON`` —
make encryption transparent at the ORM layer so repositories/services keep
working with plain Python values (``doc.content_json = {...}``,
``profile.full_name = "..."``). Encrypted values are stored in the DB as
``Text`` (Fernet tokens are base64 ASCII).
"""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings

# Default key for local/test only — rejected by the prod config validator
# (see app.core.config.Settings.validate_runtime_safety). Lets dev/test run
# without configuring FIELD_ENCRYPTION_KEYS, mirroring the MinIO default-creds
# pattern.
_DEFAULT_DEV_KEY = "2aToT_U2MCPyftyQz2VQ-Nd9uhNlSiz22RLxsJdihPM="


class FieldDecryptionError(RuntimeError):
    """Raised when an encrypted field cannot be decrypted (wrong/rotated key)."""


_fernet_cache: MultiFernet | None = None


def _fernet() -> MultiFernet:
    global _fernet_cache
    if _fernet_cache is None:
        keys = get_settings().field_encryption_keys or [_DEFAULT_DEV_KEY]
        _fernet_cache = MultiFernet([Fernet(k.encode()) for k in keys])
    return _fernet_cache


def _reset_fernet_cache() -> None:
    """Test helper: clear the cached MultiFernet after settings change."""
    global _fernet_cache
    _fernet_cache = None


def encrypt_field(plaintext: str | None) -> str | None:
    """Encrypt a string into a Fernet token string. ``None`` passes through."""
    if plaintext is None:
        return None
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_field(token: str | None) -> str | None:
    """Decrypt a Fernet token string. ``None`` passes through."""
    if token is None:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise FieldDecryptionError("Failed to decrypt field-level encrypted value") from exc


class EncryptedText(TypeDecorator[str | None]):
    """``Text`` column whose value is Fernet-encrypted at rest."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        return encrypt_field(value)

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        return decrypt_field(value)


class EncryptedJSON(TypeDecorator[Any]):
    """JSON column stored as a Fernet-encrypted ``Text`` blob at rest."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return encrypt_field(json.dumps(value, ensure_ascii=False))

    def process_result_value(self, value: str | None, dialect: Any) -> Any:
        decrypted = decrypt_field(value)
        if decrypted is None:
            return None
        return json.loads(decrypted)