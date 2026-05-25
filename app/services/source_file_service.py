# app\services\source_file_service.py

from __future__ import annotations

import re
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exceptions import AppError
from app.core.config import get_settings
from app.models import SourceFile
from app.repositories.source_file_repository import SourceFileRepository
from app.services.storage_service import StorageService


ALLOWED_FILE_KINDS = {"resume", "other"}


class SourceFileService:
    def __init__(
        self,
        source_file_repository: SourceFileRepository | None = None,
        storage_service: StorageService | None = None,
    ) -> None:
        self.source_file_repository = source_file_repository or SourceFileRepository()
        self.storage_service = storage_service or StorageService()

    async def upload_source_file(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        file_kind: str,
        upload_file: UploadFile,
    ) -> SourceFile:
        settings = get_settings()
        normalized_file_kind = file_kind.strip().lower()
        if normalized_file_kind not in ALLOWED_FILE_KINDS:
            raise AppError(
                status_code=400,
                code="invalid_file_kind",
                message=f"file_kind must be one of: {sorted(ALLOWED_FILE_KINDS)}",
                details={"allowed_file_kinds": sorted(ALLOWED_FILE_KINDS)},
            )

        original_name = upload_file.filename or "upload.bin"
        extension = Path(original_name).suffix.lower()
        if extension not in settings.allowed_upload_extensions:
            raise AppError(
                status_code=400,
                code="unsupported_file_extension",
                message="Unsupported file extension",
                details={"allowed_extensions": sorted(settings.allowed_upload_extensions)},
            )

        content_type = (upload_file.content_type or "").lower()
        if content_type not in settings.allowed_upload_content_types:
            raise AppError(
                status_code=400,
                code="unsupported_content_type",
                message="Unsupported content type",
                details={"allowed_content_types": sorted(settings.allowed_upload_content_types)},
            )

        file_bytes = await upload_file.read()

        if not file_bytes:
            raise AppError(
                status_code=400,
                code="empty_upload_file",
                message="Uploaded file is empty",
            )

        if len(file_bytes) > settings.max_upload_size_bytes:
            raise AppError(
                status_code=413,
                code="upload_file_too_large",
                message="Uploaded file is too large",
                details={"max_upload_size_bytes": settings.max_upload_size_bytes},
            )

        safe_name = self._sanitize_filename(original_name)
        storage_key = f"{user_id}/{normalized_file_kind}/{uuid.uuid4()}-{safe_name}"

        self.storage_service.upload_bytes(
            storage_key=storage_key,
            content=file_bytes,
            content_type=upload_file.content_type,
        )

        source_file = await self.source_file_repository.create(
            session,
            user_id=user_id,
            file_kind=normalized_file_kind,
            storage_key=storage_key,
            original_name=original_name,
            mime_type=upload_file.content_type,
            size_bytes=len(file_bytes),
        )

        return source_file

    async def get_source_file(
        self,
        session: AsyncSession,
        *,
        file_id: uuid.UUID,
        user_id: UUID,
    ) -> SourceFile:
        source_file = await self.source_file_repository.get_by_id(
            session,
            file_id,
            user_id=user_id,
        )
        if source_file is None:
            raise AppError(
                status_code=404,
                code="source_file_not_found",
                message="Source file not found",
            )
        return source_file

    def _sanitize_filename(self, filename: str) -> str:
        base_name = Path(filename).name.strip()
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name)
        cleaned = cleaned.strip("._")
        return cleaned or "upload.bin"
