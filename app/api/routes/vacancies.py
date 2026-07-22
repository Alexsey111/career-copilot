# app\api\routes\vacancies.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, require_quota
from app.db.session import get_db_session
from app.models import User
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.schemas.vacancy import (
    VacancyAnalysisResponse,
    VacancyImportFromFileRequest,
    VacancyImportFromUrlRequest,
    VacancyImportRequest,
    VacancyImportResponse,
    VacancyFitResponse,
    VacancyRead,
    VacancySearchItem,
    VacancySearchResponse,
)
from app.services.hh_vacancy_import_service import HHVacancyImportService
from app.services.vacancy_analysis_service import VacancyAnalysisService
from app.services.vacancy_import_service import VacancyImportService
from app.services.vacancy_fit_service import VacancyFitService
from app.services.embedding_service import EmbeddingService


router = APIRouter(prefix="/vacancies", tags=["vacancies"])


@router.get("/search", response_model=VacancySearchResponse)
async def search_vacancies(
    query: str | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    experience_level: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> VacancySearchResponse:
    repo = VacancyRepository()
    vacancies = await repo.search(
        session,
        user_id=current_user.id,
        query=query,
        location=location,
        employment_type=employment_type,
        experience_level=experience_level,
        salary_min=salary_min,
        salary_max=salary_max,
        limit=limit,
        offset=offset,
    )
    items = [
        VacancySearchItem(
            id=v.id,
            source=v.source,
            source_url=v.source_url,
            title=v.title,
            company=v.company,
            location=v.location,
            salary_from=int(v.salary_from) if v.salary_from else None,
            salary_to=int(v.salary_to) if v.salary_to else None,
            salary_currency=v.salary_currency,
            employment_type=v.employment_type,
            experience_level=v.experience_level,
            created_at=v.created_at,
        )
        for v in vacancies
    ]
    return VacancySearchResponse(items=items, total=len(items), limit=limit, offset=offset)


@router.get("/semantic-search", response_model=VacancySearchResponse)
async def semantic_search_vacancies(
    query: str,
    location: str | None = None,
    employment_type: str | None = None,
    experience_level: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    similarity_threshold: float = 0.3,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> VacancySearchResponse:
    embedding_service = EmbeddingService()
    query_embedding = embedding_service.embed_text(query)

    repo = VacancyRepository()
    results = await repo.semantic_search(
        session,
        user_id=current_user.id,
        query_embedding=query_embedding,
        query_text=query,
        location=location,
        employment_type=employment_type,
        experience_level=experience_level,
        salary_min=salary_min,
        salary_max=salary_max,
        similarity_threshold=similarity_threshold,
        limit=limit,
    )

    items = [
        VacancySearchItem(
            id=v.id,
            source=v.source,
            source_url=v.source_url,
            title=v.title,
            company=v.company,
            location=v.location,
            salary_from=int(v.salary_from) if v.salary_from else None,
            salary_to=int(v.salary_to) if v.salary_to else None,
            salary_currency=v.salary_currency,
            employment_type=v.employment_type,
            experience_level=v.experience_level,
            similarity=round(sim, 4),
            created_at=v.created_at,
        )
        for v, sim in results
    ]
    return VacancySearchResponse(items=items, total=len(items), limit=limit, offset=0)


@router.post("/import", response_model=VacancyImportResponse)
async def import_vacancy(
    payload: VacancyImportRequest,
    current_user: User = Depends(require_quota("vacancy_import")),
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
        salary_from=payload.salary_from,
        salary_to=payload.salary_to,
        salary_currency=payload.salary_currency,
        employment_type=payload.employment_type,
        experience_level=payload.experience_level,
    )

    return VacancyImportResponse(
        id=vacancy.id,
        vacancy_id=vacancy.id,
        source=vacancy.source,
        source_url=vacancy.source_url,
        title=vacancy.title,
        company=vacancy.company,
        location=vacancy.location,
        salary_from=int(vacancy.salary_from) if vacancy.salary_from else None,
        salary_to=int(vacancy.salary_to) if vacancy.salary_to else None,
        salary_currency=vacancy.salary_currency,
        employment_type=vacancy.employment_type,
        experience_level=vacancy.experience_level,
        description_length=len(vacancy.description_raw),
        created_at=vacancy.created_at,
    )


@router.post("/import-from-url", response_model=VacancyImportResponse)
async def import_vacancy_from_url(
    payload: VacancyImportFromUrlRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_quota("vacancy_import")),
) -> VacancyImportResponse:
    hh_service = HHVacancyImportService()
    vacancy_payload = hh_service.map_to_import_payload(
        await hh_service.fetch_vacancy(
            payload.source_url,
            contact_email=current_user.email,
        ),
        source_url=payload.source_url,
    )

    service = VacancyImportService()
    vacancy = await service.import_vacancy(
        session,
        user_id=current_user.id,
        **vacancy_payload,
    )

    return VacancyImportResponse(
        id=vacancy.id,
        vacancy_id=vacancy.id,
        source=vacancy.source,
        source_url=vacancy.source_url,
        title=vacancy.title,
        company=vacancy.company,
        location=vacancy.location,
        description_length=len(vacancy.description_raw or ""),
        created_at=vacancy.created_at,
    )


@router.post("/import-from-file", response_model=VacancyImportResponse)
async def import_vacancy_from_file(
    payload: VacancyImportFromFileRequest,
    current_user: User = Depends(require_quota("vacancy_import")),
    session: AsyncSession = Depends(get_db_session),
) -> VacancyImportResponse:
    service = VacancyImportService()
    vacancy = await service.import_vacancy_from_source_file(
        session,
        user_id=current_user.id,
        source_file_id=payload.source_file_id,
        title=payload.title,
        company=payload.company,
        location=payload.location,
        source_url=payload.source_url,
    )

    return VacancyImportResponse(
        id=vacancy.id,
        vacancy_id=vacancy.id,
        source=vacancy.source,
        source_url=vacancy.source_url,
        title=vacancy.title,
        company=vacancy.company,
        location=vacancy.location,
        description_length=len(vacancy.description_raw or ""),
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
        salary_from=int(vacancy.salary_from) if vacancy.salary_from else None,
        salary_to=int(vacancy.salary_to) if vacancy.salary_to else None,
        salary_currency=vacancy.salary_currency,
        employment_type=vacancy.employment_type,
        experience_level=vacancy.experience_level,
        published_at=vacancy.published_at,
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
        risks=analysis.risks_json,
        match_logic=analysis.match_logic_json,
        language_tone_hints=analysis.language_tone_hints_json,
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
        risks=analysis.risks_json,
        match_logic=analysis.match_logic_json,
        language_tone_hints=analysis.language_tone_hints_json,
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
        risks=analysis.risks_json or [],
        match_logic=analysis.match_logic_json or {},
        language_tone_hints=analysis.language_tone_hints_json or {},
        match_score=analysis.match_score,
        analysis_version=analysis.analysis_version,
        created_at=analysis.created_at,
    )


@router.get("/{vacancy_id}/fit", response_model=VacancyFitResponse)
async def get_vacancy_fit(
    vacancy_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> VacancyFitResponse:
    service = VacancyFitService()
    fit = await service.build_vacancy_fit(
        session,
        vacancy_id=vacancy_id,
        user_id=current_user.id,
    )

    return VacancyFitResponse.model_validate(fit)
