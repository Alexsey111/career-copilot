# app\api\routes\profile.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.repositories.candidate_achievement_repository import CandidateAchievementRepository
from app.schemas.achievement_extract import (
    AchievementExtractRequest,
    AchievementExtractResponse,
    AchievementItemRead,
    AchievementReviewRequest,
    AchievementReviewResponse,
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


def _achievement_item_to_read(item) -> AchievementItemRead:
    return AchievementItemRead(
        id=item.id,
        title=item.title,
        situation=item.situation,
        task=item.task,
        action=item.action,
        result=item.result,
        metric_text=item.metric_text,
        fact_status=item.fact_status,
        evidence_note=item.evidence_note,
    )


def _achievement_item_to_review_response(item) -> AchievementReviewResponse:
    return AchievementReviewResponse(
        id=item.id,
        title=item.title,
        situation=item.situation,
        task=item.task,
        action=item.action,
        result=item.result,
        metric_text=item.metric_text,
        fact_status=item.fact_status,
        evidence_note=item.evidence_note,
        updated_at=item.updated_at,
    )


@router.post("/import-resume", response_model=ResumeImportResponse)
async def import_resume(
    payload: ResumeImportRequest,
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
            _achievement_item_to_read(item)
            for item in result.achievements
            if item.id is not None
        ],
        warnings=result.warnings,
    )


@router.patch(
    "/achievements/{achievement_id}/review",
    response_model=AchievementReviewResponse,
)
async def review_achievement(
    achievement_id: UUID,
    payload: AchievementReviewRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> AchievementReviewResponse:
    if payload.title is not None and not payload.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="achievement title must not be empty",
        )

    repository = CandidateAchievementRepository()
    achievement = await repository.update_review(
        session,
        achievement_id=achievement_id,
        user_id=current_user.id,
        title=payload.title,
        situation=payload.situation,
        task=payload.task,
        action=payload.action,
        result=payload.result,
        metric_text=payload.metric_text,
        fact_status=payload.fact_status,
        evidence_note=payload.evidence_note,
    )

    if achievement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="achievement not found",
        )

    await session.commit()

    return _achievement_item_to_review_response(achievement)
