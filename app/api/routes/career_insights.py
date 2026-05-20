from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.career_insights import CareerInsightsResponse
from app.services.career_insights_service import CareerInsightsService


router = APIRouter(prefix="/career-insights", tags=["career-insights"])


@router.get("/summary", response_model=CareerInsightsResponse)
async def get_career_insights_summary(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> CareerInsightsResponse:
    service = CareerInsightsService()
    summary = await service.build_career_insights(
        session,
        user_id=current_user.id,
    )
    return CareerInsightsResponse.model_validate(summary)
