# app/services/storage/local_storage_provider.py

"""Локальный filesystem-провайдер (только dev/test, STORAGE_MODE=local)."""

from __future__ import annotations

import os
from pathlib import Path

from app.core.config import get_settings
from app.services.storage.file_storage_provider import FileStorageProvider


class LocalStorageProvider(FileStorageProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._root = Path(settings.local_storage_root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, storage_key: str) -> Path:
        # Защита от path traversal: только относительный ключ внутри root.
        base = self._root.resolve()
        target = (base / storage_key).resolve()
        if not str(target).startswith(str(base)):
            raise ValueError(f"storage_key escapes root: {storage_key}")
        return target

    def upload_bytes(
        self,
        *,
        storage_key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> str:
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return storage_key

    def download_bytes(self, *, storage_key: str) -> bytes:
        path = self._path(storage_key)
        if not path.exists():
            raise FileNotFoundError(f"storage key not found: {storage_key}")
        return path.read_bytes()

    def delete(self, *, storage_key: str) -> None:
        path = self._path(storage_key)
        try:
            path.unlink()
        except FileNotFoundError:
            return  # idempotent

    def healthcheck(self) -> bool:
        try:
            return self._root.is_dir() and os.access(self._root, os.W_OK)
        except OSError:
            return False