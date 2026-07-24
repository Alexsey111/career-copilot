# app\services\source_file_service.py

from __future__ import annotations

import re
import uuid
import hashlib
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.exceptions import AppError
from app.core.config import get_settings
from app.models import SourceFile
from app.repositories.source_file_repository import SourceFileRepository
from app.services.storage_service import StorageService


ALLOWED_FILE_KINDS = {"resume", "vacancy", "other"}


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

        content_sha256 = hashlib.sha256(file_bytes).hexdigest()
        duplicate = await self.source_file_repository.get_duplicate_by_hash(
            session,
            user_id=user_id,
            file_kind=normalized_file_kind,
            content_sha256=content_sha256,
        )
        if duplicate is not None:
            if normalized_file_kind == "resume":
                await self.source_file_repository.supersede_active_by_kind(
                    session,
                    user_id=user_id,
                    file_kind=normalized_file_kind,
                    superseded_by_id=duplicate.id,
                    exclude_id=duplicate.id,
                )
                await self.source_file_repository.activate(session, source_file=duplicate)
            return duplicate

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
            content_sha256=content_sha256,
            lifecycle_status="active",
        )
        if normalized_file_kind == "resume":
            source_file.lineage_group_id = source_file.id
            await self.source_file_repository.supersede_active_by_kind(
                session,
                user_id=user_id,
                file_kind=normalized_file_kind,
                superseded_by_id=source_file.id,
                exclude_id=source_file.id,
            )
            await session.flush()
            await session.refresh(source_file)

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

    async def get_active_resume(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> SourceFile | None:
        return await self.source_file_repository.get_active_by_kind(
            session,
            user_id=user_id,
            file_kind="resume",
        )

    async def activate_resume(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        source_file_id: UUID,
    ) -> SourceFile:
        """Сделать ранее загруженный SourceFile активным.

        Симметрично ветке дубля в ``upload_source_file`` (lines 95-104):
        supersede всех активных resume того же пользователя + activate
        указанного. 404 если не resume / чужой / не существует. Это «лёгкий»
        reuse — без reparse; FileExtraction остаётся прежний.
        """
        source_file = await self.source_file_repository.get_by_id(
            session,
            source_file_id,
            user_id=user_id,
        )
        if source_file is None:
            raise AppError(
                status_code=404,
                code="source_file_not_found",
                message="Source file not found",
            )
        if source_file.file_kind != "resume":
            raise AppError(
                status_code=400,
                code="invalid_file_kind",
                message="Only resume source files can be reactivated",
                details={"file_kind": source_file.file_kind},
            )
        if source_file.lifecycle_status == "active":
            return source_file
        await self.source_file_repository.supersede_active_by_kind(
            session,
            user_id=user_id,
            file_kind="resume",
            superseded_by_id=source_file.id,
            exclude_id=source_file.id,
        )
        return await self.source_file_repository.activate(
            session,
            source_file=source_file,
        )

    def _sanitize_filename(self, filename: str) -> str:
        base_name = Path(filename).name.strip()
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name)
        cleaned = cleaned.strip("._")
        return cleaned or "upload.bin"
