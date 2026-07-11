# app/services/storage/file_storage_provider.py

"""Абстракция хранилища файлов (ТЗ §3.5 «storage abstraction»).

Провайдер скрывает конкретное backend-хранилище (S3/MinIO, локальный диск)
за единым интерфейсом. StorageService делегирует ему операции.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class FileStorageProvider(ABC):
    @abstractmethod
    def upload_bytes(
        self,
        *,
        storage_key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> str:
        """Сохраняет bytes, возвращает storage_key."""

    @abstractmethod
    def download_bytes(self, *, storage_key: str) -> bytes:
        """Возвращает содержимое объекта. Raises, если объект не найден."""

    @abstractmethod
    def delete(self, *, storage_key: str) -> None:
        """Удаляет объект. Молчит, если объекта нет (idempotent)."""

    @abstractmethod
    def healthcheck(self) -> bool:
        """True, если хранилище доступно для записи/чтения."""

    def ensure_ready(self) -> None:
        """Гарантирует готовность (например, создаёт bucket). По умолчанию no-op."""
        return None