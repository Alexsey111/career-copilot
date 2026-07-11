# app\security\passwords.py

from __future__ import annotations

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

ph = PasswordHasher()

_ARGON2_PREFIX = "$argon2"


def hash_password(password: str) -> str:
    return ph.hash(password)


def is_argon2_hash(password_hash: str) -> bool:
    return bool(password_hash) and password_hash.startswith(_ARGON2_PREFIX)


def needs_rehash(password_hash: str) -> bool:
    """True, если хэш не argon2 (например устаревший bcrypt) — требует миграции."""
    return not is_argon2_hash(password_hash)


def verify_password(password: str, password_hash: str) -> bool:
    # Сначала пробуем текущий алгоритм (argon2).
    try:
        return ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False
    except InvalidHashError:
        # Не argon2-хэш — пробуем bcrypt fallback (устаревшие хэши).
        pass

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False