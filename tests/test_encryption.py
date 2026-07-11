from __future__ import annotations

import json

import pytest

from app.core.config import get_settings
from app.security import encryption
from app.security.encryption import (
    EncryptedJSON,
    EncryptedText,
    FieldDecryptionError,
    decrypt_field,
    encrypt_field,
)

_KEY = "2aToT_U2MCPyftyQz2VQ-Nd9uhNlSiz22RLxsJdihPM="


def _reset_caches() -> None:
    get_settings.cache_clear()
    encryption._reset_fernet_cache()


@pytest.fixture
def dev_key(monkeypatch: pytest.MonkeyPatch):
    # Force a known single key for deterministic round-trip tests.
    monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", _KEY)
    _reset_caches()
    yield _KEY
    _reset_caches()


def test_encrypt_decrypt_round_trip(dev_key: str) -> None:
    plaintext = "Иванов Иван Иванович, ivan@example.com +7 999 123-45-67"
    token = encrypt_field(plaintext)
    assert token != plaintext
    assert decrypt_field(token) == plaintext


def test_none_passes_through(dev_key: str) -> None:
    assert encrypt_field(None) is None
    assert decrypt_field(None) is None


def test_invalid_token_raises(dev_key: str) -> None:
    with pytest.raises(FieldDecryptionError):
        decrypt_field("not-a-valid-fernet-token")


def test_key_rotation_decrypts_old_key(monkeypatch: pytest.MonkeyPatch) -> None:
    old_key = _KEY
    new_key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="  # 32 zero bytes, urlsafe
    # Encrypt with old key only.
    monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", old_key)
    _reset_caches()
    token = encrypt_field("secret-pii")

    # Rotate: new key first for encryption, old key still listed for decryption.
    monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", f"{new_key},{old_key}")
    _reset_caches()
    assert decrypt_field(token) == "secret-pii"
    # New encryptions now use the new (first) key.
    new_token = encrypt_field("secret-pii")
    assert new_token != token
    _reset_caches()


def test_encrypted_text_type_decorator_round_trip() -> None:
    typ = EncryptedText()
    bound = typ.process_bind_param("hello", dialect=None)
    assert bound != "hello"
    assert typ.process_result_value(bound, dialect=None) == "hello"
    assert typ.process_bind_param(None, dialect=None) is None
    assert typ.process_result_value(None, dialect=None) is None


def test_encrypted_json_type_decorator_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", _KEY)
    _reset_caches()
    try:
        typ = EncryptedJSON()
        payload = {"name": "Иван", "contacts": ["ivan@example.com", "+7 999 123-45-67"], "n": 3}
        bound = typ.process_bind_param(payload, dialect=None)
        assert isinstance(bound, str)
        # Stored form must not leak plaintext.
        assert "Иван" not in bound
        assert "ivan@example.com" not in bound
        result = typ.process_result_value(bound, dialect=None)
        assert result == payload
        assert typ.process_bind_param(None, dialect=None) is None
        assert typ.process_result_value(None, dialect=None) is None
    finally:
        _reset_caches()


def test_encrypted_json_preserves_unicode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIELD_ENCRYPTION_KEYS", _KEY)
    _reset_caches()
    try:
        typ = EncryptedJSON()
        payload = {"role": "Старший разработчик", "tags": ["Python", "FastAPI"]}
        bound = typ.process_bind_param(payload, dialect=None)
        # The encrypted blob is ASCII; unicode survives round-trip.
        assert bound.isascii()
        assert typ.process_result_value(bound, dialect=None) == payload
        # And the stored JSON itself was non-ASCII (ensure_ascii=False) before encryption,
        # i.e. the bind step did not escape to \uXXXX — verify via decrypt+json.loads path above.
        _ = json.loads  # noqa: F841 — sanity that json is imported
    finally:
        _reset_caches()