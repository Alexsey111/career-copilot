# app/services/storage_service.py

from __future__ import annotations

from app.services.storage.factory import create_storage_provider
from app.services.storage.file_storage_provider import FileStorageProvider


class StorageService:
    """Фасад над FileStorageProvider.

    Сохраняет публичный API (upload_bytes/download_bytes) для вызывающего кода
    и тестовых фикстур; делегирует реализацию провайдеру, выбранному по
    STORAGE_MODE. Добавляет delete и healthcheck.
    """

    def __init__(self, provider: FileStorageProvider | None = None) -> None:
        self.provider = provider if provider is not None else create_storage_provider()

    def ensure_bucket_exists(self) -> None:
        self.provider.ensure_ready()

    def upload_bytes(
        self,
        *,
        storage_key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> str:
        return self.provider.upload_bytes(
            storage_key=storage_key,
            content=content,
            content_type=content_type,
        )

    def download_bytes(self, *, storage_key: str) -> bytes:
        return self.provider.download_bytes(storage_key=storage_key)

    def delete(self, *, storage_key: str) -> None:
        self.provider.delete(storage_key=storage_key)

    def healthcheck(self) -> bool:
        return self.provider.healthcheck()