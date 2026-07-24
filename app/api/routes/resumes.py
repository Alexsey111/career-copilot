"""API: листинг + reuse ранее загруженных резюме (``/profile/resumes``).

Сценарий: пользователь уже загружал PDF/DOCX/TXT, прошёл extract-structured,
потом хочет переключиться на старую версию (без повторной загрузки файла)
или перепарсить (если, например, поправил `Parse Diagnostics` и хочет
перепарсить без ручного reupload).

Используется:
- ``SourceFileRepository.list_by_user_and_kind`` — список
- ``FileExtractionRepository.get_latest_for_source_files`` (batch) — preview
- ``SourceFileService.activate_resume`` — лёгкий reuse (без reparse)
- ``ProfileImportService.import_resume(force_reparse=True)`` — reuse с reparse
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.source_file_repository import SourceFileRepository
from app.schemas.resume_history import (
    ResumeListItem,
    ResumeListResponse,
    ResumeReuseResponse,
)
from app.services.profile_import_service import ProfileImportService
from app.services.source_file_service import SourceFileService


router = APIRouter(prefix="/profile/resumes", tags=["resumes"])


_TEXT_PREVIEW_LIMIT = 500


def _to_list_item(
    source_file,
    latest_extraction,
    active_id: UUID | None,
) -> ResumeListItem:
    detected_format: str | None = None
    text_preview: str | None = None
    if latest_extraction is not None:
        meta = latest_extraction.extracted_metadata_json or {}
        detected_format = meta.get("detected_format") if isinstance(meta, dict) else None
        if latest_extraction.extracted_text:
            text_preview = latest_extraction.extracted_text[:_TEXT_PREVIEW_LIMIT]
    return ResumeListItem(
        id=source_file.id,
        file_kind=source_file.file_kind,
        original_name=source_file.original_name,
        mime_type=source_file.mime_type,
        size_bytes=source_file.size_bytes,
        content_sha256=source_file.content_sha256,
        lifecycle_status=source_file.lifecycle_status,
        lineage_group_id=source_file.lineage_group_id,
        superseded_by_id=source_file.superseded_by_id,
        created_at=source_file.created_at,
        updated_at=source_file.updated_at,
        latest_extraction_id=latest_extraction.id if latest_extraction else None,
        latest_extraction_status=latest_extraction.status if latest_extraction else None,
        text_preview=text_preview,
        detected_format=detected_format,
        extracted_at=latest_extraction.created_at if latest_extraction else None,
        is_active=source_file.lifecycle_status == "active",
        # Reuse запрещён, если запись уже активна — нечего «реактивировать».
        is_reusable=source_file.lifecycle_status != "active",
    )


@router.get("", response_model=ResumeListResponse)
async def list_resumes(
    include_superseded: bool = Query(
        True,
        description="Включать ли superseded-версии (история загрузок).",
    ),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ResumeListResponse:
    source_file_repo = SourceFileRepository()
    extraction_repo = FileExtractionRepository()

    files = await source_file_repo.list_by_user_and_kind(
        session,
        user_id=current_user.id,
        file_kind="resume",
        include_superseded=include_superseded,
    )
    if not files:
        active = await source_file_repo.get_active_by_kind(
            session, user_id=current_user.id, file_kind="resume",
        )
        return ResumeListResponse(
            items=[],
            total=0,
            active_source_file_id=active.id if active else None,
        )

    latest_by_id = await extraction_repo.get_latest_for_source_files(
        session,
        source_file_ids=[f.id for f in files],
    )

    active = await source_file_repo.get_active_by_kind(
        session, user_id=current_user.id, file_kind="resume",
    )

    items = [
        _to_list_item(
            source_file=f,
            latest_extraction=latest_by_id.get(f.id),
            active_id=active.id if active else None,
        )
        for f in files
    ]
    return ResumeListResponse(
        items=items,
        total=len(items),
        active_source_file_id=active.id if active else None,
    )


@router.post("/{source_file_id}/reuse", response_model=ResumeReuseResponse)
async def reuse_resume(
    source_file_id: UUID,
    reparse: bool = Query(
        False,
        description="Если true — повторно парсить файл из storage (новый FileExtraction). "
                    "По умолчанию false — активировать готовый extraction без reparse.",
    ),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ResumeReuseResponse:
    source_file_repo = SourceFileRepository()
    extraction_repo = FileExtractionRepository()
    source_file_service = SourceFileService()

    # Ownership + existence — get_by_id с user_id (404 на чужой/несуществующий).
    source_file = await source_file_repo.get_by_id(
        session,
        source_file_id,
        user_id=current_user.id,
    )
    if source_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source file not found",
        )
    if source_file.file_kind != "resume":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only resume source files can be reused",
        )

    # Активируем выбранный SourceFile (supersede остальных, activate его).
    activated = await source_file_service.activate_resume(
        session,
        user_id=current_user.id,
        source_file_id=source_file_id,
    )

    latest_extraction = await extraction_repo.get_latest_for_source_file(
        session,
        source_file_id=source_file_id,
    )

    if reparse:
        import_service = ProfileImportService()
        try:
            profile, new_extraction, detected_format = await import_service.import_resume(
                session,
                source_file_id=source_file_id,
                user_id=current_user.id,
                force_reparse=True,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        preview = new_extraction.extracted_text[:1000]
        return ResumeReuseResponse(
            profile_id=profile.id,
            source_file_id=source_file_id,
            extraction_id=new_extraction.id,
            status=new_extraction.status,
            detected_format=detected_format,
            text_length=len(new_extraction.extracted_text),
            text_preview=preview,
            reparse_performed=True,
            reused=False,
            created_at=new_extraction.created_at,
        )

    # Без reparse — отдаём последний extraction (или 404, если парсинга не было).
    if latest_extraction is None:
        # Файл загружен, но никогда не парсился. Возвращаем activated, но
        # без extraction_id — пускай клиент вызовет /profile/import-resume.
        return ResumeReuseResponse(
            profile_id=None,
            source_file_id=activated.id,
            extraction_id=None,
            status="needs_import",
            detected_format=None,
            text_length=None,
            text_preview=None,
            reparse_performed=False,
            reused=False,
            created_at=activated.updated_at,
        )

    preview = latest_extraction.extracted_text[:1000]
    meta = latest_extraction.extracted_metadata_json or {}
    detected_format = meta.get("detected_format") if isinstance(meta, dict) else None
    return ResumeReuseResponse(
        source_file_id=activated.id,
        extraction_id=latest_extraction.id,
        status=latest_extraction.status,
        detected_format=detected_format,
        text_length=len(latest_extraction.extracted_text),
        text_preview=preview,
        reparse_performed=False,
        reused=True,
        created_at=latest_extraction.created_at,
    )
