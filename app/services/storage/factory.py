# app/services/storage/factory.py

"""Фабрика провайдеров хранилища по STORAGE_MODE."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.storage.file_storage_provider import FileStorageProvider
from app.services.storage.local_storage_provider import LocalStorageProvider
from app.services.storage.s3_storage_provider import S3StorageProvider


def create_storage_provider() -> FileStorageProvider:
    settings = get_settings()
    mode = settings.storage_mode

    if mode in {"minio", "s3"}:
        return S3StorageProvider()
    if mode == "local":
        return LocalStorageProvider()

    raise RuntimeError(f"Unsupported storage mode: {mode}")