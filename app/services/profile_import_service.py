# app\services\profile_import_service.py

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile, FileExtraction
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.source_file_repository import SourceFileRepository
from app.services.resume_parser_service import ResumeParserService
from app.services.storage_service import StorageService


class ProfileImportService:
    def __init__(
        self,
        source_file_repository: SourceFileRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        file_extraction_repository: FileExtractionRepository | None = None,
        storage_service: StorageService | None = None,
        resume_parser_service: ResumeParserService | None = None,
    ) -> None:
        self.source_file_repository = source_file_repository or SourceFileRepository()
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.file_extraction_repository = file_extraction_repository or FileExtractionRepository()
        self.storage_service = storage_service or StorageService()
        self.resume_parser_service = resume_parser_service or ResumeParserService()

    async def import_resume(
        self,
        session: AsyncSession,
        *,
        source_file_id,
        user_id: UUID,
        force_reparse: bool = False,
    ) -> tuple[CandidateProfile, FileExtraction, str]:
        source_file = await self.source_file_repository.get_by_id(
            session,
            source_file_id,
            user_id=user_id,
        )
        if source_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="source file not found",
            )

        if source_file.file_kind != "resume":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source file is not a resume",
            )

        profile = await self.candidate_profile_repository.get_by_user_id(
            session,
            user_id,
        )
        if profile is None:
            profile = await self.candidate_profile_repository.create_empty(
                session,
                user_id=user_id,
            )

        existing_extraction = await self.file_extraction_repository.get_latest_for_source_file(
            session,
            source_file_id=source_file.id,
        )
        if existing_extraction is not None and not force_reparse:
            await session.refresh(profile)
            return profile, existing_extraction, str(
                (existing_extraction.extracted_metadata_json or {}).get("detected_format")
                or "cached"
            )

        file_bytes = self.storage_service.download_bytes(storage_key=source_file.storage_key)

        parsed = self.resume_parser_service.parse(
            file_bytes=file_bytes,
            mime_type=source_file.mime_type,
            filename=source_file.original_name,
        )

        extraction = await self.file_extraction_repository.create(
            session,
            source_file_id=source_file.id,
            status="completed",
            parser_name="local_resume_parser",
            parser_version="v1",
            extracted_text=parsed.text,
            extracted_metadata_json={
                **parsed.metadata,
                "detected_format": parsed.detected_format,
            },
        )

        await session.flush()
        await session.refresh(profile)
        await session.refresh(extraction)

        return profile, extraction, parsed.detected_format

    async def import_resume_from_text(
        self,
        session: AsyncSession,
        *,
        text: str,
        user_id: UUID,
    ) -> tuple[CandidateProfile, FileExtraction, str]:
        profile = await self.candidate_profile_repository.get_by_user_id(
            session,
            user_id,
        )
        if profile is None:
            profile = await self.candidate_profile_repository.create_empty(
                session,
                user_id=user_id,
            )

        extraction = await self.file_extraction_repository.create(
            session,
            source_file_id=None,
            status="completed",
            parser_name="text_import",
            parser_version="v1",
            extracted_text=text,
            extracted_metadata_json={"detected_format": "text"},
        )

        await session.flush()
        await session.refresh(profile)
        await session.refresh(extraction)

        return profile, extraction, "text"
