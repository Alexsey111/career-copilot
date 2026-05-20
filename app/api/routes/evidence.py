# app\api\routes\evidence.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.schemas.evidence import (
    EvidenceInsightsResponse,
    EvidenceSnippetItem,
    EvidenceUsageItem,
)
from app.services.evidence_insights_service import EvidenceInsightsService


router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/snippets", response_model=list[EvidenceSnippetItem])
async def list_evidence_snippets(
    source_type: list[str] | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[EvidenceSnippetItem]:
    repository = EvidenceSnippetRepository()
    snippets = await repository.list_by_user_id(
        session,
        user_id=current_user.id,
        source_types=source_type,
    )
    return [EvidenceSnippetItem.model_validate(item) for item in snippets]


@router.get("/snippets/{snippet_id}", response_model=EvidenceSnippetItem)
async def get_evidence_snippet(
    snippet_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceSnippetItem:
    repository = EvidenceSnippetRepository()
    snippet = await repository.get_by_id_for_user(
        session,
        user_id=current_user.id,
        snippet_id=snippet_id,
    )
    if snippet is None:
        raise HTTPException(status_code=404, detail="Evidence snippet not found")

    return EvidenceSnippetItem.model_validate(snippet)


@router.get("/usages", response_model=list[EvidenceUsageItem])
async def list_evidence_usages(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[EvidenceUsageItem]:
    repository = EvidenceSnippetRepository()
    usages = await repository.list_usages_by_user_id(
        session,
        user_id=current_user.id,
    )
    return [EvidenceUsageItem.model_validate(item) for item in usages]


@router.get("/insights", response_model=EvidenceInsightsResponse)
async def get_evidence_insights(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceInsightsResponse:
    service = EvidenceInsightsService()
    insights = await service.get_evidence_insights(session, user_id=current_user.id)
    return EvidenceInsightsResponse.model_validate(insights)
