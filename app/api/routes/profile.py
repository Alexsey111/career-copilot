# app\api\routes\profile.py

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_dev_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.achievement_extract import (
    AchievementExtractRequest,
    AchievementExtractResponse,
    AchievementItemRead,
)
from app.schemas.profile_import import ResumeImportRequest, ResumeImportResponse
from app.schemas.profile_structured import (
    StructuredProfileExtractRequest,
    StructuredProfileExtractResponse,
)
from app.services.achievement_extraction_service import AchievementExtractionService
from app.services.profile_import_service import ProfileImportService
from app.services.profile_structuring_service import ProfileStructuringService


router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("/import-resume", response_model=ResumeImportResponse)
async def import_resume(
    payload: ResumeImportRequest,
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> ResumeImportResponse:
    service = ProfileImportService()
    profile, extraction, detected_format = await service.import_resume(
        session,
        source_file_id=payload.source_file_id,
        user_id=current_user.id,
    )

    preview = extraction.extracted_text[:1000]

    return ResumeImportResponse(
        profile_id=profile.id,
        source_file_id=extraction.source_file_id,
        extraction_id=extraction.id,
        status=extraction.status,
        detected_format=detected_format,
        text_length=len(extraction.extracted_text),
        text_preview=preview,
        created_at=extraction.created_at,
    )


@router.post("/extract-structured", response_model=StructuredProfileExtractResponse)
async def extract_structured_profile(
    payload: StructuredProfileExtractRequest,
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> StructuredProfileExtractResponse:
    service = ProfileStructuringService()
    profile, draft = await service.extract_into_profile(
        session,
        extraction_id=payload.extraction_id,
        user_id=current_user.id,
    )

    return StructuredProfileExtractResponse(
        profile_id=profile.id,
        extraction_id=payload.extraction_id,
        full_name=profile.full_name,
        headline=profile.headline,
        location=profile.location,
        target_roles=profile.target_roles_json,
        experience_count=len(draft.experiences),
        warnings=draft.warnings,
    )


@router.post("/extract-achievements", response_model=AchievementExtractResponse)
async def extract_achievements(
    payload: AchievementExtractRequest,
    current_user: User = Depends(get_current_dev_user),
    session: AsyncSession = Depends(get_db_session),
) -> AchievementExtractResponse:
    service = AchievementExtractionService()
    result = await service.extract_achievements(
        session,
        extraction_id=payload.extraction_id,
        user_id=current_user.id,
    )

    return AchievementExtractResponse(
        profile_id=result.profile.id,
        extraction_id=payload.extraction_id,
        achievement_count=len(result.achievements),
        achievements=[
            AchievementItemRead(
                title=item.title,
                fact_status=item.fact_status,
            )
            for item in result.achievements
        ],
        warnings=result.warnings,
    )
