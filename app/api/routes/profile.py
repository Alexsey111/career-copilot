# app\api\routes\profile.py

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_active_user,
    require_ai_consent,
    require_data_processing_consent,
    require_quota,
)
from app.db.session import get_db_session
from app.models import User
from app.repositories.candidate_achievement_repository import CandidateAchievementRepository
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.source_file_repository import SourceFileRepository
from app.schemas.achievement_extract import (
    AchievementExtractRequest,
    AchievementExtractResponse,
    AchievementItemRead,
    AchievementReviewRequest,
    AchievementReviewResponse,
)
from app.schemas.profile_import import ResumeImportRequest, ResumeImportResponse
from app.schemas.parse_diagnostics import (
    ParseDiagnosticsRequest,
    ParseDiagnosticsResponse,
)
from app.schemas.career_strategy import CareerStrategyResponse
from app.schemas.target_track import (
    TargetTrackCreate,
    TargetTrackResponse,
    TargetTrackUpdate,
)
from app.schemas.profile_intake import (
    GitHubPublicProfileImportRequest,
    GitHubProfileIntakeRequest,
    ManualProfileIntakeRequest,
    MarketUpdateRequest,
    ProfileIntakeResponse,
)
from app.schemas.profile_structured import (
    StructuredProfileExtractRequest,
    StructuredProfileExtractResponse,
)
from app.services.achievement_extraction_service import AchievementExtractionService
from app.services.career_strategy_service import CareerStrategyService
from app.services.github_public_import_service import (
    GitHubPublicImportError,
    GitHubPublicImportService,
)
from app.services.profile_import_service import ProfileImportService
from app.services.profile_intake_service import ProfileIntakeService
from app.services.profile_structuring_service import ProfileStructuringService
from app.services.repository_achievement_service import RepositoryAchievementService


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


def _intake_result_to_response(result) -> ProfileIntakeResponse:
    return ProfileIntakeResponse(
        profile_id=result.profile.id,
        source_file_id=result.source_file_id,
        extraction_id=result.extraction_id,
        source=result.source,
        status="completed",
        full_name=result.profile.full_name,
        location=result.profile.location,
        market=result.profile.market,
        target_roles=result.profile.target_roles_json,
        experience_count=len(result.experiences),
        project_count=result.project_count,
        achievement_count=len(result.achievements),
        evidence_snippet_count=len(result.evidence_snippets),
        technologies=result.technologies,
        ai_tools=result.ai_tools,
        automation_tools=result.automation_tools,
        raw_text_preview=result.raw_text[:1000],
        created_at=result.profile.created_at,
    )


@router.get("/resume-state")
async def get_resume_pipeline_state(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    extraction_repository = FileExtractionRepository()
    profile_repository = CandidateProfileRepository()

    extraction = await extraction_repository.get_latest_for_active_source_file_kind(
        session,
        current_user.id,
        file_kind="resume",
    )
    profile = await profile_repository.get_with_related_by_user_id(
        session,
        current_user.id,
    )

    resume_import = None
    if extraction is not None:
        detected_format = str(
            (extraction.extracted_metadata_json or {}).get("detected_format") or ""
        )
        resume_import = {
            "profile_id": profile.id if profile is not None else None,
            "source_file_id": extraction.source_file_id,
            "extraction_id": extraction.id,
            "status": extraction.status,
            "detected_format": detected_format,
            "text_length": len(extraction.extracted_text or ""),
            "text_preview": (extraction.extracted_text or "")[:1000],
            "created_at": extraction.created_at,
        }

    structured_profile = None
    achievements = None
    if profile is not None:
        structured_profile = {
            "profile_id": profile.id,
            "extraction_id": extraction.id if extraction is not None else None,
            "full_name": profile.full_name,
            "headline": profile.headline,
            "location": profile.location,
            "market": profile.market,
            "target_roles": profile.target_roles_json or [],
            "experience_count": len(profile.experiences or []),
            "project_count": 0,
            "internship_count": 0,
            "achievement_signal_count": len(profile.achievements or []),
            "evidence_snippet_count": 0,
            "technologies": profile.technologies_json or [],
            "ai_tools": [],
            "automation_tools": [],
            "competency_signal_count": 0,
            "structured_evidence": [],
            "warnings": [],
        }
        achievements = {
            "profile_id": profile.id,
            "extraction_id": extraction.id if extraction is not None else None,
            "achievement_count": len(profile.achievements or []),
            "achievements": [
                _achievement_item_to_read(item).model_dump(mode="json")
                for item in (profile.achievements or [])
                if item.id is not None
            ],
            "warnings": [],
        }

    return {
        "resume_import": resume_import,
        "structured_profile": structured_profile,
        "achievements": achievements,
    }


@router.post("/intake/manual", response_model=ProfileIntakeResponse)
async def intake_manual_profile(
    payload: ManualProfileIntakeRequest,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> ProfileIntakeResponse:
    service = ProfileIntakeService()
    try:
        result = await service.ingest_manual_profile(
            session,
            user_id=current_user.id,
            payload=payload,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return _intake_result_to_response(result)


@router.post("/intake/github", response_model=ProfileIntakeResponse)
async def intake_github_profile(
    payload: GitHubProfileIntakeRequest,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> ProfileIntakeResponse:
    service = ProfileIntakeService()
    try:
        result = await service.ingest_github_profile(
            session,
            user_id=current_user.id,
            payload=payload,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return _intake_result_to_response(result)


@router.post("/intake/github-public", response_model=ProfileIntakeResponse)
async def intake_github_public_profile(
    payload: GitHubPublicProfileImportRequest,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> ProfileIntakeResponse:
    service = GitHubPublicImportService()
    try:
        result = await service.import_public_profile(
            session,
            user_id=current_user.id,
            payload=payload,
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except GitHubPublicImportError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception:
        await session.rollback()
        raise

    return _intake_result_to_response(result)


@router.post("/import-resume", response_model=ResumeImportResponse)
async def import_resume(
    payload: ResumeImportRequest,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> ResumeImportResponse:
    service = ProfileImportService()
    try:
        profile, extraction, detected_format = await service.import_resume(
            session,
            source_file_id=payload.source_file_id,
            user_id=current_user.id,
            force_reparse=payload.force_reparse,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

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


from app.schemas.json_contracts import StrictBaseModel


class ResumeTextImportRequest(StrictBaseModel):
    text: str


@router.post("/import-resume-text", response_model=ResumeImportResponse)
async def import_resume_text(
    payload: ResumeTextImportRequest,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> ResumeImportResponse:
    service = ProfileImportService()
    profile, extraction, detected_format = await service.import_resume_from_text(
        session,
        text=payload.text,
        user_id=current_user.id,
    )
    await session.commit()

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
    current_user: User = Depends(require_ai_consent),
    session: AsyncSession = Depends(get_db_session),
    _quota: User = Depends(require_quota("ai_request")),
) -> StructuredProfileExtractResponse:
    service = ProfileStructuringService()
    try:
        profile, draft = await service.extract_into_profile(
            session,
            extraction_id=payload.extraction_id,
            user_id=current_user.id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return StructuredProfileExtractResponse(
        profile_id=profile.id,
        extraction_id=payload.extraction_id,
        full_name=profile.full_name,
        headline=profile.headline,
        location=profile.location,
        contacts=draft.contacts.as_dict(),
        market=profile.market,
        target_roles=profile.target_roles_json,
        experience_count=len(draft.experiences),
        project_count=len(draft.projects),
        internship_count=len(draft.internships),
        achievement_signal_count=len(draft.achievements),
        evidence_snippet_count=len(draft.evidence_snippets),
        technologies=draft.technologies,
        ai_tools=draft.ai_tools,
        automation_tools=draft.automation_tools,
        competency_signal_count=len(draft.competency_signals),
        structured_evidence=[item.as_dict() for item in draft.evidence_snippets],
        warnings=draft.warnings,
    )


@router.post("/extract-achievements", response_model=AchievementExtractResponse)
async def extract_achievements(
    payload: AchievementExtractRequest,
    current_user: User = Depends(require_ai_consent),
    session: AsyncSession = Depends(get_db_session),
    _quota: User = Depends(require_quota("ai_request")),
) -> AchievementExtractResponse:
    service = AchievementExtractionService()
    try:
        result = await service.extract_achievements(
            session,
            extraction_id=payload.extraction_id,
            user_id=current_user.id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

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


@router.post("/repository-achievements/generate", response_model=AchievementExtractResponse)
async def generate_repository_achievements(
    current_user: User = Depends(require_ai_consent),
    session: AsyncSession = Depends(get_db_session),
    _quota: User = Depends(require_quota("ai_request")),
) -> AchievementExtractResponse:
    profile_repository = CandidateProfileRepository()
    profile = await profile_repository.get_with_related_by_user_id(
        session,
        current_user.id,
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="candidate profile not found",
        )

    service = RepositoryAchievementService()
    try:
        result = await service.generate_repository_achievement_drafts(
            session,
            user_id=current_user.id,
            profile_id=profile.id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return AchievementExtractResponse(
        profile_id=profile.id,
        extraction_id=result.extraction_id,
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


@router.patch("/market")
async def update_market(
    payload: MarketUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    # Этап 7: переключатель юрисдикции/рынка (RU/EU/US). Валидация Literal в схеме.
    profile_repo = CandidateProfileRepository()
    profile = await profile_repo.get_by_user_id(session, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="profile not found",
        )

    profile.market = payload.market
    await session.commit()

    return {"market": profile.market}
async def delete_profile(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    from app.models import CandidateProfile

    profile = await session.get(CandidateProfile, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="profile not found",
        )

    await session.delete(profile)
    await session.commit()
    return {"status": "deleted"}


@router.get("/target-tracks", response_model=list[TargetTrackResponse])
async def list_target_tracks(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TargetTrackResponse]:
    profile_repo = CandidateProfileRepository()
    profile = await profile_repo.get_with_related_by_user_id(session, current_user.id)
    if profile is None:
        return []

    return [TargetTrackResponse.from_model(track) for track in profile.target_tracks]


@router.post("/target-tracks", response_model=TargetTrackResponse)
async def create_target_track(
    payload: TargetTrackCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> TargetTrackResponse:
    from app.models import CandidateTargetTrack

    profile_repo = CandidateProfileRepository()
    profile = await profile_repo.get_with_related_by_user_id(session, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="profile not found",
        )

    track = CandidateTargetTrack(
        profile_id=profile.id,
        name=payload.name,
        target_roles_json=list(payload.target_roles),
        salary_expectation=payload.salary_expectation,
        salary_currency=payload.salary_currency,
        location_preferences_json=list(payload.location_preferences),
        work_format_json=dict(payload.work_format),
        priority=payload.priority,
        is_active=payload.is_active,
        notes=payload.notes,
        order_index=payload.order_index,
    )
    session.add(track)
    await session.commit()
    await session.refresh(track)

    return TargetTrackResponse.from_model(track)


@router.patch("/target-tracks/{track_id}", response_model=TargetTrackResponse)
async def update_target_track(
    track_id: UUID,
    payload: TargetTrackUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> TargetTrackResponse:
    """Этап 9.D: partial update target-track (ownership через profile.user_id)."""
    profile_repo = CandidateProfileRepository()
    profile = await profile_repo.get_with_related_by_user_id(session, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="target track not found",
        )

    track = next(
        (t for t in profile.target_tracks if t.id == track_id),
        None,
    )
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="target track not found",
        )

    payload.apply_to(track)
    await session.commit()
    await session.refresh(track)

    return TargetTrackResponse.from_model(track)


@router.delete("/target-tracks/{track_id}")
async def delete_target_track(
    track_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    profile_repo = CandidateProfileRepository()
    profile = await profile_repo.get_with_related_by_user_id(session, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="target track not found",
        )

    track = next(
        (t for t in profile.target_tracks if t.id == track_id),
        None,
    )
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="target track not found",
        )

    await session.delete(track)
    await session.commit()
    return {"status": "deleted"}


@router.get(
    "/target-tracks/{track_id}/strategy",
    response_model=CareerStrategyResponse,
)
async def get_target_track_strategy(
    track_id: UUID,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> CareerStrategyResponse:
    """Этап 9.D: карьерная стратегия для target-track.

    Детерминированный, explainable отчёт on-demand: gap_summary (recurring gaps,
    классифицированные на relevant/other относительно target_roles трека),
    learning_plan (rule-based шаги reskilling/upskilling, без ссылок на курсы),
    search_tactics (тактика поиска/нетворкинга по типу ролей + gap severity),
    provenance (источники, confidence low/medium нечисловой, requires_human_review
    всегда True). Без AI (non-goal career_strategy.md), без миграции БД.
    """
    service = CareerStrategyService()
    summary = await service.build_strategy(
        session,
        user_id=current_user.id,
        track_id=track_id,
    )
    return CareerStrategyResponse.model_validate(summary)


@router.post("/parse-diagnostics", response_model=ParseDiagnosticsResponse)
async def get_parse_diagnostics(
    payload: ParseDiagnosticsRequest,
    current_user: User = Depends(require_data_processing_consent),
    session: AsyncSession = Depends(get_db_session),
) -> ParseDiagnosticsResponse:
    """Этап 8: отчёт «как видит парсер» по загруженному резюме.

    Возвращает распознанные блоки (секции) и их порядок, потерянные фрагменты,
    структурные warnings (таблицы/колонки/длинные строки/скан-риск) и anti-hack
    находки скрытого текста + метаданные файла. Отчёт считается при импорте и
    кэшируется в ``FileExtraction.extracted_metadata_json["parse_diagnostics"]``;
    если отсутствует (старый импорт) — пересчитывается частично из текста.
    """
    source_file_repo = SourceFileRepository()
    source_file = await source_file_repo.get_by_id(
        session,
        payload.source_file_id,
        user_id=current_user.id,
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

    extraction_repo = FileExtractionRepository()
    extraction = await extraction_repo.get_latest_for_source_file(
        session,
        source_file_id=source_file.id,
    )
    if extraction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no extraction found; import the resume first",
        )

    metadata = extraction.extracted_metadata_json or {}
    diagnostics_dict = metadata.get("parse_diagnostics")

    if not diagnostics_dict:
        # Совместимость со старыми extractions (до Этапа 8): частичный пересчёт
        # из текста — без hidden-text/метаданных (нужен исходный файл).
        from app.services.parse_diagnostics_service import ParseDiagnosticsService
        from app.services.resume_parser_service import ParsedResume

        detected = metadata.get("detected_format") or "text"
        partial = ParsedResume(
            text=extraction.extracted_text or "",
            detected_format=detected,
            metadata={
                "diagnostics_seed": {
                    "zero_width": {"count": 0, "sample": ""},
                    "hidden_text": [],
                    "file_metadata": {},
                },
            },
        )
        diagnostics_dict = ParseDiagnosticsService().build_report(partial).as_dict()

    return ParseDiagnosticsResponse.model_validate(diagnostics_dict)
