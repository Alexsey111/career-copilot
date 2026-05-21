# app/api/routes/review_summary.py

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.review_summary import ReviewSummaryResponse
from app.services.review_summary_service import ReviewSummaryService


router = APIRouter(prefix="/review/summary", tags=["review-summary"])


@router.get("/{entity_type}/{entity_id}", response_model=ReviewSummaryResponse)
async def get_review_summary(
    entity_type: Literal["document", "interview_prep"],
    entity_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> ReviewSummaryResponse:
    service = ReviewSummaryService()
    summary = await service.build_summary(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=current_user.id,
    )
    return ReviewSummaryResponse.model_validate(summary)
