# app\api\routes\vacancies.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db_session
from app.models import User
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.schemas.vacancy import (
    VacancyAnalysisResponse,
    VacancyImportRequest,
    VacancyImportResponse,
    VacancyRead,
)
from app.services.vacancy_analysis_service import VacancyAnalysisService
from app.services.vacancy_import_service import VacancyImportService


router = APIRouter(prefix="/vacancies", tags=["vacancies"])


@router.post("/import", response_model=VacancyImportResponse)
async def import_vacancy(
    payload: VacancyImportRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> VacancyImportResponse:
    service = VacancyImportService()
    vacancy = await service.import_vacancy(
        session,
        user_id=current_user.id,
        source=payload.source,
        source_url=payload.source_url,
        external_id=payload.external_id,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        description_raw=payload.description_raw,
    )

    return VacancyImportResponse(
        id=vacancy.id,
        vacancy_id=vacancy.id,
        source=vacancy.source,
        source_url=vacancy.source_url,
        title=vacancy.title,
        company=vacancy.company,
        location=vacancy.location,
        description_length=len(vacancy.description_raw),
        created_at=vacancy.created_at,
    )


@router.get("/{vacancy_id}", response_model=VacancyRead)
async def get_vacancy(
    vacancy_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> VacancyRead:
    repo = VacancyRepository()
    vacancy = await repo.get_by_id(
        session,
        vacancy_id,
        user_id=current_user.id,
    )
    if vacancy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="vacancy not found",
        )
    if vacancy.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="vacancy not found",
        )

    return VacancyRead(
        id=vacancy.id,
        source=vacancy.source,
        source_url=vacancy.source_url,
        external_id=vacancy.external_id,
        title=vacancy.title,
        company=vacancy.company,
        location=vacancy.location,
        description_raw=vacancy.description_raw,
        description_length=len(vacancy.description_raw),
        created_at=vacancy.created_at,
        updated_at=vacancy.updated_at,
    )


@router.post("/{vacancy_id}/analyze", response_model=VacancyAnalysisResponse)
async def analyze_vacancy(
    vacancy_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> VacancyAnalysisResponse:
    service = VacancyAnalysisService()
    analysis = await service.analyze_vacancy(
        session,
        vacancy_id=vacancy_id,
        user_id=current_user.id,
    )

    return VacancyAnalysisResponse(
        analysis_id=analysis.id,
        vacancy_id=analysis.vacancy_id,
        must_have=analysis.must_have_json,
        nice_to_have=analysis.nice_to_have_json,
        keywords=analysis.keywords_json,
        strengths=analysis.strengths_json,
        gaps=analysis.gaps_json,
        match_score=analysis.match_score,
        analysis_version=analysis.analysis_version,
        created_at=analysis.created_at,
    )


@router.get("/{vacancy_id}/analysis/latest", response_model=VacancyAnalysisResponse)
async def get_latest_vacancy_analysis(
    vacancy_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> VacancyAnalysisResponse:
    vacancy_repo = VacancyRepository()
    vacancy = await vacancy_repo.get_by_id(
        session,
        vacancy_id,
        user_id=current_user.id,
    )
    if vacancy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="vacancy not found",
        )
    if vacancy.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="vacancy not found",
        )

    repo = VacancyAnalysisRepository()
    # FIX: добавлен user_id=current_user.id
    analysis = await repo.get_latest_for_vacancy(session, vacancy_id, user_id=current_user.id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="vacancy analysis not found",
        )

    return VacancyAnalysisResponse(
        analysis_id=analysis.id,
        vacancy_id=analysis.vacancy_id,
        must_have=analysis.must_have_json,
        nice_to_have=analysis.nice_to_have_json,
        keywords=analysis.keywords_json,
        strengths=analysis.strengths_json,
        gaps=analysis.gaps_json,
        match_score=analysis.match_score,
        analysis_version=analysis.analysis_version,
        created_at=analysis.created_at,
    )


@router.post("/{vacancy_id}/match", response_model=VacancyAnalysisResponse)
async def match_vacancy(
    vacancy_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    service = VacancyAnalysisService()

    analysis = await service.match_vacancy(
        session,
        vacancy_id=vacancy_id,
        user_id=current_user.id,
    )

    await session.commit()

    return VacancyAnalysisResponse(
        analysis_id=analysis.id,
        vacancy_id=analysis.vacancy_id,
        must_have=analysis.must_have_json or [],
        nice_to_have=analysis.nice_to_have_json or [],
        keywords=analysis.keywords_json or [],
        strengths=analysis.strengths_json or [],
        gaps=analysis.gaps_json or [],
        match_score=analysis.match_score,
        analysis_version=analysis.analysis_version,
        created_at=analysis.created_at,
    )
