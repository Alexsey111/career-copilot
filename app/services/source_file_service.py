# app\services\source_file_service.py

from __future__ import annotations

import re
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceFile
from app.repositories.source_file_repository import SourceFileRepository
from app.services.storage_service import StorageService


MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
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
        normalized_file_kind = file_kind.strip().lower()
        if normalized_file_kind not in ALLOWED_FILE_KINDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"file_kind must be one of: {sorted(ALLOWED_FILE_KINDS)}",
            )

        original_name = upload_file.filename or "upload.bin"
        file_bytes = await upload_file.read()

        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="uploaded file is empty",
            )

        if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"file is too large, max size is {MAX_UPLOAD_SIZE_BYTES} bytes",
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

        await session.commit()
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="file not found",
            )
        return source_file

    def _sanitize_filename(self, filename: str) -> str:
        base_name = Path(filename).name.strip()
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name)
        cleaned = cleaned.strip("._")
        return cleaned or "upload.bin"
