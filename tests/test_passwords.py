from __future__ import annotations

import bcrypt

from app.security.passwords import (
    hash_password,
    is_argon2_hash,
    needs_rehash,
    verify_password,
)


def _bcrypt_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def test_hash_password_produces_argon2_hash():
    h = hash_password("S3cret-Password!")
    assert is_argon2_hash(h)
    assert not needs_rehash(h)


def test_verify_argon2_correct_password():
    h = hash_password("Correct-123!")
    assert verify_password("Correct-123!", h) is True


def test_verify_argon2_wrong_password_returns_false():
    h = hash_password("Correct-123!")
    assert verify_password("wrong-password", h) is False


def test_verify_bcrypt_fallback_correct_password():
    h = _bcrypt_hash("Legacy-123!")
    assert needs_rehash(h)
    assert verify_password("Legacy-123!", h) is True


def test_verify_bcrypt_fallback_wrong_password_returns_false():
    h = _bcrypt_hash("Legacy-123!")
    assert verify_password("not-the-password", h) is False


def test_verify_unknown_hash_format_returns_false():
    assert verify_password("whatever", "not-a-real-hash") is False


def test_needs_rehash_true_for_bcrypt_false_for_argon2():
    assert needs_rehash(_bcrypt_hash("x")) is True
    assert needs_rehash(hash_password("x")) is False


def test_login_migration_rehashes_bcrypt_to_argon2():
    # Эмулируем миграцию при логине: bcrypt хэш → argon2.
    old_hash = _bcrypt_hash("Migrate-123!")
    assert needs_rehash(old_hash)

    # Успешный verify через fallback, затем re-hash.
    assert verify_password("Migrate-123!", old_hash) is True
    new_hash = hash_password("Migrate-123!")
    assert is_argon2_hash(new_hash)
    assert not needs_rehash(new_hash)
    # Новый хэш проверяется напрямую argon2-путём.
    assert verify_password("Migrate-123!", new_hash) is True
    # Старый пароль не подходит к новому хэшу под другим значением.
    assert verify_password("wrong", new_hash) is False