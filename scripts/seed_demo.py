from __future__ import annotations

import copy
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
import sys
from pathlib import Path

from sqlalchemy import delete

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import AsyncSessionLocal
from app.models import (
    AIRun,
    ApplicationEvent,
    ApplicationRecord,
    ApplicationStatusHistory,
    CandidateAchievement,
    CandidateExperience,
    CandidateProfile,
    DocumentReview,
    DocumentVersion,
    EvidenceSnippet,
    EvidenceUsage,
    FileExtraction,
    InterviewPrepSession,
    InterviewSession,
    RefreshSession,
    SourceFile,
    User,
    VacancyAnalysis,
    Vacancy,
)
from app.repositories.application_event_repository import ApplicationEventRepository
from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.application_status_history_repository import (
    ApplicationStatusHistoryRepository,
)
from app.repositories.candidate_achievement_repository import (
    CandidateAchievementRepository,
)
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.source_file_repository import SourceFileRepository
from app.repositories.user_repository import UserRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.security.passwords import hash_password
from app.services.application_tracking_service import ApplicationTrackingService
from app.services.cover_letter_generation_service import CoverLetterGenerationService
from app.services.document_review_service import DocumentReviewService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.interview_prep_service import InterviewPrepService
from app.services.resume_generation_service import ResumeGenerationService
from app.services.vacancy_analysis_service import VacancyAnalysisService
from app.services.vacancy_import_service import VacancyImportService


DEMO_EMAIL = "demo.candidate@career-copilot.local"
DEMO_PASSWORD = "DemoPass123!"

RESUME_TEXT = """Анна
Соколова
г. Москва

ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ
Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes, SQL, stakeholder communication

ЖЕЛАЕМАЯ ДОЛЖНОСТЬ
Senior Backend Engineer, Platform Engineer

ОПЫТ РАБОТЫ
Acme Platform, Backend Engineer
01.01.2021 - по настоящее время

ОПЫТ РАБОТЫ
Northwind Labs, Python Developer
01.01.2018 - 31.12.2020
"""

MAIN_VACANCY = {
    "title": "Senior Backend Engineer",
    "company": "Northwind Labs",
    "location": "Remote",
    "description_raw": """Требования:
- Python
- FastAPI
- PostgreSQL
- Kubernetes
- Stakeholder communication

Будет плюсом:
- Redis
- System design
- Docker
""",
}

PLATFORM_VACANCY = {
    "title": "Platform Engineer",
    "company": "Atlas Systems",
    "location": "Remote",
    "description_raw": """Требования:
- Kubernetes
- System design
- AWS
- Leadership

Будет плюсом:
- Observability
- Incident response
""",
}

LEAD_VACANCY = {
    "title": "Backend Team Lead",
    "company": "Blue River",
    "location": "Hybrid",
    "description_raw": """Требования:
- Leadership
- Stakeholder communication
- System design
- Kubernetes

Будет плюсом:
- Coaching
- Hiring
""",
}


@dataclass(slots=True)
class DemoArtifacts:
    user_id: str
    vacancy_ids: list[str]
    analysis_ids: list[str]
    resume_document_id: str
    cover_letter_document_id: str
    trust_cover_letter_document_id: str
    application_ids: list[str]
    prep_session_id: str


async def _delete_existing_demo_user(session) -> None:
    repo = UserRepository()
    existing = await repo.get_by_email(session, DEMO_EMAIL)
    if existing is None:
        return

    user_id = existing.id

    # Use explicit SQL deletes to avoid ORM cascade/lazy-load side effects during demo reset.
    await session.execute(delete(ApplicationStatusHistory).where(ApplicationStatusHistory.application.has(user_id=user_id)))
    await session.execute(delete(ApplicationEvent).where(ApplicationEvent.application.has(user_id=user_id)))
    await session.execute(delete(ApplicationRecord).where(ApplicationRecord.user_id == user_id))
    await session.execute(delete(InterviewPrepSession).where(InterviewPrepSession.user_id == user_id))
    await session.execute(delete(InterviewSession).where(InterviewSession.user_id == user_id))
    await session.execute(delete(DocumentVersion).where(DocumentVersion.user_id == user_id))
    await session.execute(delete(VacancyAnalysis).where(VacancyAnalysis.vacancy.has(user_id=user_id)))
    await session.execute(delete(Vacancy).where(Vacancy.user_id == user_id))
    await session.execute(delete(EvidenceUsage).where(EvidenceUsage.user_id == user_id))
    await session.execute(delete(EvidenceSnippet).where(EvidenceSnippet.user_id == user_id))
    await session.execute(delete(CandidateAchievement).where(CandidateAchievement.profile.has(user_id=user_id)))
    await session.execute(delete(CandidateProfile).where(CandidateProfile.user_id == user_id))
    await session.execute(delete(FileExtraction).where(FileExtraction.source_file.has(user_id=user_id)))
    await session.execute(delete(SourceFile).where(SourceFile.user_id == user_id))
    await session.execute(delete(DocumentReview).where(DocumentReview.user_id == user_id))
    await session.execute(delete(AIRun).where(AIRun.user_id == user_id))
    await session.execute(delete(RefreshSession).where(RefreshSession.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


async def _create_demo_user(session) -> User:
    repo = UserRepository()
    user = await repo.create(
        session,
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        auth_provider="local",
    )
    user.is_active = True
    user.is_verified = True
    await session.commit()
    await session.refresh(user)
    return user


async def _seed_source_resume(
    session,
    *,
    user: User,
) -> tuple[SourceFile, FileExtraction, CandidateProfile, list[CandidateAchievement]]:
    source_file_repo = SourceFileRepository()
    extraction_repo = FileExtractionRepository()
    profile_repo = CandidateProfileRepository()
    achievement_repo = CandidateAchievementRepository()

    source_file = await source_file_repo.create(
        session,
        user_id=user.id,
        file_kind="resume",
        storage_key="demo/demo-resume-source.txt",
        original_name="demo_resume.txt",
        mime_type="text/plain; charset=utf-8",
        size_bytes=len(RESUME_TEXT.encode("utf-8")),
    )

    await extraction_repo.create(
        session,
        source_file_id=source_file.id,
        status="completed",
        parser_name="demo_seed",
        parser_version="1",
        extracted_text=RESUME_TEXT,
        extracted_metadata_json={
            "filename": "demo_resume.txt",
            "mime_type": "text/plain; charset=utf-8",
            "source": "seed_demo",
        },
    )

    profile = await profile_repo.create_empty(session, user_id=user.id)
    profile.full_name = "Анна Соколова"
    profile.headline = "Senior Backend Engineer"
    profile.location = "Москва"
    profile.summary = (
        "Python backend engineer with product-minded delivery, stakeholder communication, "
        "and platform reliability focus."
    )
    profile.target_roles_json = ["Senior Backend Engineer", "Platform Engineer"]
    profile.work_format_preferences_json = {
        "remote": True,
        "hybrid": True,
        "onsite": False,
    }

    experiences = [
        CandidateExperience(
            profile_id=profile.id,
            company="Acme Platform",
            role="Backend Engineer",
            start_date=None,
            end_date=None,
            description_raw=(
                "Built FastAPI services with PostgreSQL and Redis, introduced Docker-based "
                "deployment flows, and improved stakeholder communication for release planning."
            ),
            order_index=0,
        ),
        CandidateExperience(
            profile_id=profile.id,
            company="Northwind Labs",
            role="Python Developer",
            start_date=None,
            end_date=None,
            description_raw=(
                "Designed system integrations, supported Kubernetes rollout discussions, "
                "and coordinated cross-functional release work."
            ),
            order_index=1,
        ),
    ]
    session.add_all(experiences)

    achievements = await achievement_repo.replace_for_profile(
        session,
        profile_id=profile.id,
        achievements=[
            {
                "title": "Built a FastAPI service that reduced manual handoffs",
                "situation": "The team had a manual workflow that slowed releases.",
                "task": "Automate the backend handoff flow.",
                "action": "Implemented FastAPI endpoints with PostgreSQL persistence.",
                "result": "Reduced manual handoffs by 35%.",
                "metric_text": "35% fewer manual handoffs",
                "evidence_note": "Reviewed in the resume import workflow.",
                "fact_status": "confirmed",
            },
            {
                "title": "Led stakeholder planning for a platform release",
                "situation": "A release had many moving parts across teams.",
                "task": "Align delivery dates and dependencies.",
                "action": "Ran stakeholder planning and coordinated the release checklist.",
                "result": "The release shipped on schedule with clear ownership.",
                "metric_text": "On-time release",
                "evidence_note": "Stakeholder coordination example.",
                "fact_status": "confirmed",
            },
            {
                "title": "Designed deployment automation with Docker",
                "situation": "Local and staging environments were inconsistent.",
                "task": "Standardize deployment flows.",
                "action": "Packaged services with Docker and documented rollout steps.",
                "result": "Deployment errors dropped and handoff became repeatable.",
                "metric_text": "Fewer deployment errors",
                "evidence_note": "Platform and release story.",
                "fact_status": "confirmed",
            },
        ],
    )

    await session.commit()
    await session.refresh(profile)
    for achievement in achievements:
        await session.refresh(achievement)

    return source_file, await extraction_repo.get_latest_for_user(session, user.id), profile, achievements


async def _seed_evidence(
    session,
    *,
    user: User,
    achievements: list[CandidateAchievement],
) -> list[dict[str, Any]]:
    extraction_service = EvidenceExtractionService()
    repository = EvidenceSnippetRepository()

    achievement_dicts = [
        {
            "id": str(item.id),
            "title": item.title,
            "situation": item.situation,
            "task": item.task,
            "action": item.action,
            "result": item.result,
            "metric_text": item.metric_text,
            "evidence_note": item.evidence_note,
            "fact_status": item.fact_status,
        }
        for item in achievements
    ]

    extracted = extraction_service.extract_from_achievements(
        achievement_dicts,
        user_id=str(user.id),
        source_type="achievement",
    )

    manual_snippets = [
        {
            "fingerprint": f"demo-manual-kubernetes-{user.id}",
            "title": "Kubernetes rollout notes",
            "snippet_text": (
                "Documented Kubernetes rollout constraints and system design questions, "
                "but the work is still only partially verified."
            ),
            "source_type": "manual",
            "skills": ["kubernetes", "system_design"],
            "evidence_strength": "weak",
            "fact_status": "partial",
            "usage_count": 0,
            "used_in_documents_count": 0,
            "used_in_interviews_count": 0,
            "star_summary": {
                "situation": "Rollout planning was needed",
                "task": "Describe the deployment path",
                "action": "",
                "result": "",
            },
        },
        {
            "fingerprint": f"demo-manual-leadership-{user.id}",
            "title": "Leadership sync notes",
            "snippet_text": (
                "Captured a leadership story about stakeholder communication and release planning."
            ),
            "source_type": "manual",
            "skills": ["leadership", "stakeholder_communication"],
            "evidence_strength": "medium",
            "fact_status": "confirmed",
            "usage_count": 0,
            "used_in_documents_count": 0,
            "used_in_interviews_count": 0,
            "star_summary": {
                "situation": "Release coordination",
                "task": "Align teams",
                "action": "Ran stakeholder syncs",
                "result": "",
            },
        },
    ]

    persisted = await repository.upsert_many(
        session,
        user_id=user.id,
        snippets=[extraction_service.snippet_to_dict(snippet) for snippet in extracted]
        + manual_snippets,
    )
    await session.commit()
    return [
        {
            "id": str(snippet.id),
            "title": snippet.title,
            "strength": snippet.evidence_strength,
            "fact_status": snippet.fact_status,
        }
        for snippet in persisted
    ]


async def _seed_vacancies_and_analysis(
    session,
    *,
    user: User,
) -> tuple[list[Vacancy], list[str]]:
    import_service = VacancyImportService()
    analysis_service = VacancyAnalysisService()

    vacancy_specs = [MAIN_VACANCY, PLATFORM_VACANCY, LEAD_VACANCY]
    vacancies: list[Vacancy] = []
    analysis_ids: list[str] = []
    for spec in vacancy_specs:
        vacancy = await import_service.import_vacancy(
            session,
            user_id=user.id,
            source="manual",
            source_url=None,
            external_id=None,
            title=spec["title"],
            company=spec["company"],
            location=spec["location"],
            description_raw=spec["description_raw"],
        )
        vacancies.append(vacancy)

    for vacancy in vacancies:
        analysis = await analysis_service.analyze_vacancy(
            session,
            vacancy_id=vacancy.id,
            user_id=user.id,
        )
        analysis_ids.append(str(analysis.id))

    return vacancies, analysis_ids


async def _seed_documents(
    session,
    *,
    user: User,
    vacancy: Vacancy,
) -> tuple[DocumentVersion, DocumentVersion, DocumentVersion]:
    resume_service = ResumeGenerationService()
    cover_letter_service = CoverLetterGenerationService()
    review_service = DocumentReviewService()

    resume_document = await resume_service.generate_resume(
        session,
        vacancy_id=vacancy.id,
        user_id=user.id,
    )
    cover_letter_document = await cover_letter_service.generate_cover_letter(
        session,
        vacancy_id=vacancy.id,
        user_id=user.id,
    )

    await review_service.review_document(
        session,
        document_id=resume_document.id,
        user_id=user.id,
        review_status="approved",
        review_comment="Seeded demo resume approved",
        set_active_when_approved=True,
    )
    await review_service.review_document(
        session,
        document_id=cover_letter_document.id,
        user_id=user.id,
        review_status="approved",
        review_comment="Seeded demo cover letter approved",
        set_active_when_approved=True,
    )

    repo = DocumentVersionRepository()
    approved_resume = await repo.get_by_id(session, resume_document.id, user_id=user.id)
    approved_cover_letter = await repo.get_by_id(session, cover_letter_document.id, user_id=user.id)

    if approved_resume is None or approved_cover_letter is None:
        raise RuntimeError("Failed to seed approved documents")

    trust_cover_letter = await _create_trust_risk_cover_letter_variant(
        session,
        user=user,
        source_document=approved_cover_letter,
    )

    return approved_resume, approved_cover_letter, trust_cover_letter


async def _create_trust_risk_cover_letter_variant(
    session,
    *,
    user: User,
    source_document: DocumentVersion,
) -> DocumentVersion:
    document_repo = DocumentVersionRepository()

    content_json = copy.deepcopy(source_document.content_json or {})
    sections = content_json.setdefault("sections", {})
    meta = content_json.setdefault("meta", {})
    provenance = content_json.setdefault("provenance", meta.get("provenance") or {})

    risky_claims = [
        {
            "claim_type": "achievement",
            "text": "Led platform migration that improved reliability across teams",
            "fact_status": "needs_confirmation",
            "source": "seed_demo",
        },
        {
            "claim_type": "achievement",
            "text": "Reduced deployment time to under five minutes",
            "fact_status": "partial",
            "source": "seed_demo",
        },
    ]

    sections["claims_needing_confirmation"] = risky_claims
    sections["warnings"] = list(sections.get("warnings") or []) + [
        {
            "code": "seeded_trust_risk",
            "message": "Seeded demo cover letter intentionally includes claims requiring confirmation",
            "severity": "warning",
        }
    ]

    provenance["confidence"] = 0.34
    provenance["confidence_level"] = "needs_review"
    provenance["requires_human_review"] = True

    meta["confidence"] = 0.34
    meta["provenance"] = provenance
    meta["generated_at"] = meta.get("generated_at") or datetime.now(timezone.utc).isoformat()

    trust_document = await document_repo.create(
        session,
        user_id=user.id,
        vacancy_id=source_document.vacancy_id,
        derived_from_id=source_document.id,
        analysis_id=source_document.analysis_id,
        document_kind=source_document.document_kind,
        version_label="cover_letter_trust_demo_v1",
        review_status="draft",
        is_active=True,
        content_json=content_json,
        rendered_text=source_document.rendered_text,
        source_recommendation_id=source_document.source_recommendation_id,
    )
    await document_repo.deactivate_same_scope(
        session,
        user_id=user.id,
        vacancy_id=source_document.vacancy_id,
        document_kind=source_document.document_kind,
        exclude_document_id=trust_document.id,
    )
    await session.commit()
    await session.refresh(trust_document)
    return trust_document


async def _seed_application_trackers(
    session,
    *,
    user: User,
    main_vacancy: Vacancy,
    resume_document: DocumentVersion,
    cover_letter_document: DocumentVersion,
    extra_vacancies: list[Vacancy],
) -> list[ApplicationRecord]:
    tracking_service = ApplicationTrackingService()
    application_repo = ApplicationRecordRepository()
    status_history_repo = ApplicationStatusHistoryRepository()
    event_repo = ApplicationEventRepository()

    created_application = await tracking_service.create_application(
        session,
        user_id=user.id,
        vacancy_id=main_vacancy.id,
        resume_document_id=resume_document.id,
        cover_letter_document_id=cover_letter_document.id,
        source="manual",
        notes="Seeded demo application record.",
    )
    await tracking_service.update_status(
        session,
        application_id=created_application.id,
        user_id=user.id,
        status_value="ready",
        notes="Ready after seeded review pass.",
    )
    applied_application = await tracking_service.submit_application(
        session,
        application_id=created_application.id,
        user_id=user.id,
        source="manual",
        external_link=None,
    )

    rejected_vacancy = extra_vacancies[0]
    rejected_application = await application_repo.create(
        session,
        user_id=user.id,
        vacancy_id=rejected_vacancy.id,
        status="rejected",
        source="manual",
        notes="Seeded historical application that ended in rejection.",
        applied_at=datetime.now(timezone.utc) - timedelta(days=3),
        outcome="rejected",
    )
    await status_history_repo.create(
        session,
        application_id=rejected_application.id,
        previous_status=None,
        new_status="draft",
        notes="Seeded record created.",
    )
    await status_history_repo.create(
        session,
        application_id=rejected_application.id,
        previous_status="draft",
        new_status="ready",
        notes="Seeded record marked ready.",
    )
    await status_history_repo.create(
        session,
        application_id=rejected_application.id,
        previous_status="ready",
        new_status="applied",
        notes="Seeded manual submission.",
    )
    await status_history_repo.create(
        session,
        application_id=rejected_application.id,
        previous_status="applied",
        new_status="interview",
        notes="Interview reached in the demo history.",
    )
    await status_history_repo.create(
        session,
        application_id=rejected_application.id,
        previous_status="interview",
        new_status="rejected",
        notes="Rejected after interview.",
    )
    await event_repo.create(
        session,
        application_id=rejected_application.id,
        event_type="application_created",
        title="Application created",
        description="Seeded rejected application record.",
        meta_json={"source": "seed_demo"},
    )
    await event_repo.create(
        session,
        application_id=rejected_application.id,
        event_type="application_applied",
        title="Application submitted manually",
        description="Manual submission recorded for analytics.",
        meta_json={
            "source": "manual",
            "external_link": None,
            "applied_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        },
    )
    await event_repo.create(
        session,
        application_id=rejected_application.id,
        event_type="outcome_recorded",
        title="Outcome recorded",
        description="Rejected after interview.",
        meta_json={"outcome": "rejected"},
    )

    offer_vacancy = extra_vacancies[1]
    offer_application = await application_repo.create(
        session,
        user_id=user.id,
        vacancy_id=offer_vacancy.id,
        status="offer",
        source="manual",
        notes="Seeded historical application that reached offer.",
        applied_at=datetime.now(timezone.utc) - timedelta(days=6),
        outcome="offer",
    )
    await status_history_repo.create(
        session,
        application_id=offer_application.id,
        previous_status=None,
        new_status="draft",
        notes="Seeded record created.",
    )
    await status_history_repo.create(
        session,
        application_id=offer_application.id,
        previous_status="draft",
        new_status="ready",
        notes="Seeded record marked ready.",
    )
    await status_history_repo.create(
        session,
        application_id=offer_application.id,
        previous_status="ready",
        new_status="applied",
        notes="Seeded manual submission.",
    )
    await status_history_repo.create(
        session,
        application_id=offer_application.id,
        previous_status="applied",
        new_status="screening",
        notes="Screening passed in the demo history.",
    )
    await status_history_repo.create(
        session,
        application_id=offer_application.id,
        previous_status="screening",
        new_status="interview",
        notes="Interview reached in the demo history.",
    )
    await status_history_repo.create(
        session,
        application_id=offer_application.id,
        previous_status="interview",
        new_status="offer",
        notes="Offer received.",
    )
    await event_repo.create(
        session,
        application_id=offer_application.id,
        event_type="application_created",
        title="Application created",
        description="Seeded offer application record.",
        meta_json={"source": "seed_demo"},
    )
    await event_repo.create(
        session,
        application_id=offer_application.id,
        event_type="application_applied",
        title="Application submitted manually",
        description="Manual submission recorded for analytics.",
        meta_json={
            "source": "manual",
            "external_link": None,
            "applied_at": (datetime.now(timezone.utc) - timedelta(days=6)).isoformat(),
        },
    )
    await event_repo.create(
        session,
        application_id=offer_application.id,
        event_type="outcome_recorded",
        title="Outcome recorded",
        description="Offer received.",
        meta_json={"outcome": "offer"},
    )

    await session.commit()
    return [applied_application, rejected_application, offer_application]


async def _seed_interview_prep(
    session,
    *,
    user: User,
    application: ApplicationRecord,
) -> str:
    service = InterviewPrepService()
    prep_session = await service.create_session(
        session,
        user_id=user.id,
        application_id=application.id,
    )
    return str(prep_session.id)


async def seed_demo() -> DemoArtifacts:
    async with AsyncSessionLocal() as session:
        await _delete_existing_demo_user(session)
        user = await _create_demo_user(session)

        _, _, profile, achievements = await _seed_source_resume(
            session,
            user=user,
        )
        await _seed_evidence(session, user=user, achievements=achievements)
        vacancies, analysis_ids = await _seed_vacancies_and_analysis(session, user=user)
        resume_document, cover_letter_document, trust_cover_letter_document = await _seed_documents(
            session,
            user=user,
            vacancy=vacancies[0],
        )
        applications = await _seed_application_trackers(
            session,
            user=user,
            main_vacancy=vacancies[0],
            resume_document=resume_document,
            cover_letter_document=cover_letter_document,
            extra_vacancies=vacancies[1:],
        )
        prep_session_id = await _seed_interview_prep(
            session,
            user=user,
            application=applications[0],
        )

        return DemoArtifacts(
            user_id=str(user.id),
            vacancy_ids=[str(vacancy.id) for vacancy in vacancies],
            analysis_ids=analysis_ids,
            resume_document_id=str(resume_document.id),
            cover_letter_document_id=str(cover_letter_document.id),
            trust_cover_letter_document_id=str(trust_cover_letter_document.id),
            application_ids=[str(application.id) for application in applications],
            prep_session_id=prep_session_id,
        )


async def main() -> None:
    artifacts = await seed_demo()
    print("Demo seed complete")
    print(f"Demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print(f"User id: {artifacts.user_id}")
    print(f"Resume document: {artifacts.resume_document_id}")
    print(f"Cover letter document: {artifacts.cover_letter_document_id}")
    print(f"Trust cover letter document: {artifacts.trust_cover_letter_document_id}")
    print(f"Applications: {', '.join(artifacts.application_ids)}")
    print(f"Interview prep session: {artifacts.prep_session_id}")
    print("Demo application is an internal tracker record.")
    print("No external application is submitted.")


if __name__ == "__main__":
    asyncio.run(main())
