# tests/test_storage_abstraction.py

"""Этап 3 — абстракция хранилища файлов (ТЗ §3.5 storage abstraction)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.storage.factory import create_storage_provider
from app.services.storage.file_storage_provider import FileStorageProvider
from app.services.storage.local_storage_provider import LocalStorageProvider
from app.services.storage_service import StorageService


def _enable_local_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("STORAGE_MODE", "local")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()


def test_factory_returns_local_provider(monkeypatch, tmp_path):
    _enable_local_storage(monkeypatch, tmp_path)
    try:
        provider = create_storage_provider()
        assert isinstance(provider, LocalStorageProvider)
        assert isinstance(provider, FileStorageProvider)
    finally:
        get_settings.cache_clear()


def test_factory_returns_s3_provider_for_minio(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_MODE", "minio")
    get_settings.cache_clear()
    try:
        provider = create_storage_provider()
        assert provider.__class__.__name__ == "S3StorageProvider"
    finally:
        get_settings.cache_clear()


def test_local_provider_roundtrip(monkeypatch, tmp_path):
    _enable_local_storage(monkeypatch, tmp_path)
    try:
        provider = create_storage_provider()
        provider.upload_bytes(storage_key="u/1/file.pdf", content=b"hello", content_type="application/pdf")
        assert provider.download_bytes(storage_key="u/1/file.pdf") == b"hello"
    finally:
        get_settings.cache_clear()


def test_local_provider_delete_is_idempotent(monkeypatch, tmp_path):
    _enable_local_storage(monkeypatch, tmp_path)
    try:
        provider = create_storage_provider()
        provider.upload_bytes(storage_key="f.bin", content=b"x")
        provider.delete(storage_key="f.bin")
        # Повторное удаление не падает.
        provider.delete(storage_key="f.bin")
        with pytest.raises(FileNotFoundError):
            provider.download_bytes(storage_key="f.bin")
    finally:
        get_settings.cache_clear()


def test_local_provider_healthcheck(monkeypatch, tmp_path):
    _enable_local_storage(monkeypatch, tmp_path)
    try:
        provider = create_storage_provider()
        assert provider.healthcheck() is True
    finally:
        get_settings.cache_clear()


def test_local_provider_rejects_path_traversal(monkeypatch, tmp_path):
    _enable_local_storage(monkeypatch, tmp_path)
    try:
        provider = create_storage_provider()
        with pytest.raises(ValueError):
            provider.upload_bytes(storage_key="../../etc/evil", content=b"x")
    finally:
        get_settings.cache_clear()


def test_storage_service_delegates_delete_and_healthcheck(monkeypatch, tmp_path):
    _enable_local_storage(monkeypatch, tmp_path)
    try:
        service = StorageService()
        service.upload_bytes(storage_key="a/b.txt", content=b"data")
        assert service.download_bytes(storage_key="a/b.txt") == b"data"
        service.delete(storage_key="a/b.txt")
        assert service.healthcheck() is True
    finally:
        get_settings.cache_clear()