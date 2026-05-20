# app\services\interview_prep_service.py

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.application_record_repository import ApplicationRecordRepository
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.interview_prep_session_repository import (
    InterviewPrepSessionRepository,
)
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.domain.evidence import EvidenceSourceType
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.evidence_selection_service import EvidenceSelectionService
from app.services.interview_question_service import InterviewQuestionService
from app.services.interview_readiness_service import InterviewReadinessService


class InterviewPrepService:
    def __init__(
        self,
        *,
        application_repository: ApplicationRecordRepository | None = None,
        vacancy_repository: VacancyRepository | None = None,
        vacancy_analysis_repository: VacancyAnalysisRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        prep_session_repository: InterviewPrepSessionRepository | None = None,
        evidence_snippet_repository: EvidenceSnippetRepository | None = None,
        question_service: InterviewQuestionService | None = None,
        readiness_service: InterviewReadinessService | None = None,
        evidence_extraction_service: EvidenceExtractionService | None = None,
        evidence_selection_service: EvidenceSelectionService | None = None,
    ) -> None:
        self.application_repository = (
            application_repository or ApplicationRecordRepository()
        )
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.vacancy_analysis_repository = (
            vacancy_analysis_repository or VacancyAnalysisRepository()
        )
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.prep_session_repository = (
            prep_session_repository or InterviewPrepSessionRepository()
        )
        self.evidence_snippet_repository = (
            evidence_snippet_repository or EvidenceSnippetRepository()
        )
        self.question_service = question_service or InterviewQuestionService()
        self.readiness_service = readiness_service or InterviewReadinessService()
        self.evidence_extraction_service = (
            evidence_extraction_service or EvidenceExtractionService()
        )
        self.evidence_selection_service = (
            evidence_selection_service or EvidenceSelectionService()
        )

    async def create_session(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        application_id: UUID,
    ):
        existing_session = await self.prep_session_repository.get_by_application_id(
            session,
            user_id=user_id,
            application_id=application_id,
        )
        if existing_session is not None:
            return existing_session

        snapshot = await self.build_session_snapshot(
            session,
            user_id=user_id,
            application_id=application_id,
        )

        prep_session = await self.prep_session_repository.create(
            session,
            user_id=user_id,
            vacancy_id=snapshot["vacancy_id"],
            application_id=application_id,
            prep_status=snapshot["prep_status"],
            readiness_score=snapshot["readiness_score"],
            competency_map_json=snapshot["competency_map"],
            question_set_json=snapshot["questions"],
            evidence_links_json=snapshot["evidence_links"],
            weak_areas_json=snapshot["weak_areas"],
            readiness_json=snapshot["readiness"],
        )
        await session.commit()
        await session.refresh(prep_session)
        return prep_session

    async def build_session_snapshot(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        application_id: UUID,
    ) -> dict[str, Any]:
        application = await self.application_repository.get_by_id(
            session,
            application_id,
            user_id=user_id,
        )
        if application is None or application.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="application not found",
            )

        vacancy = await self.vacancy_repository.get_by_id(
            session,
            application.vacancy_id,
            user_id=user_id,
        )
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        analysis = await self.vacancy_analysis_repository.get_latest_for_vacancy(
            session,
            vacancy.id,
            user_id=user_id,
        )
        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="vacancy analysis not found; run vacancy analysis first",
            )

        profile = await self.candidate_profile_repository.get_with_related_by_user_id(
            session,
            user_id,
        )
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="candidate profile not found; run profile extraction first",
            )

        confirmed_achievements = [
            self._achievement_to_dict(item)
            for item in (profile.achievements or [])
            if str(item.fact_status or "").strip().lower() == "confirmed"
        ]
        evidence_snippet_drafts = self.evidence_extraction_service.extract_from_achievements(
            confirmed_achievements,
            user_id=str(user_id),
            source_type=EvidenceSourceType.ACHIEVEMENT,
        )
        persisted_snippets = await self.evidence_snippet_repository.upsert_many(
            session,
            user_id=user_id,
            snippets=[
                self.evidence_extraction_service.snippet_to_dict(snippet)
                for snippet in evidence_snippet_drafts
            ],
        )
        competency_map = self.question_service.build_competency_map(
            vacancy=vacancy,
            analysis=analysis,
        )
        evidence_snippets = [self._evidence_snippet_to_dict(item) for item in persisted_snippets]
        ranked_evidence_snippets = self._rank_evidence_snippets(
            vacancy=vacancy,
            analysis=analysis,
            competency_map=competency_map,
            evidence_snippets=evidence_snippets,
        )

        weak_areas = self.readiness_service.build_weak_areas(
            competency_map=competency_map,
            confirmed_achievements=confirmed_achievements,
        )
        questions = self.question_service.build_question_set(
            vacancy=vacancy,
            competency_map=competency_map,
            confirmed_achievements=confirmed_achievements,
            weak_areas=weak_areas,
            evidence_snippets=ranked_evidence_snippets,
        )
        evidence_links = self.question_service.build_evidence_links(
            questions=questions,
            confirmed_achievements=confirmed_achievements,
            evidence_snippets=ranked_evidence_snippets,
        )
        for link in evidence_links:
            evidence_id = link.get("achievement_id")
            if not evidence_id:
                continue
            try:
                await self.evidence_snippet_repository.record_usage(
                    session,
                    user_id=user_id,
                    evidence_snippet_id=UUID(str(evidence_id)),
                    usage_type="interview",
                    target_type="question",
                    target_id=str(link.get("question_id") or ""),
                    note=str(link.get("reason") or "").strip() or None,
                )
            except Exception:
                continue
        readiness = self.readiness_service.build_readiness(
            competency_map=competency_map,
            weak_areas=weak_areas,
            evidence_links=evidence_links,
        )
        prep_status = "ready" if readiness["ready"] else "draft"

        return {
            "vacancy_id": vacancy.id,
            "competency_map": competency_map,
            "questions": questions,
            "evidence_links": evidence_links,
            "weak_areas": weak_areas,
            "readiness": readiness,
            "readiness_score": readiness["score"],
            "prep_status": prep_status,
        }

    def _rank_evidence_snippets(
        self,
        *,
        vacancy,
        analysis,
        competency_map: dict[str, Any],
        evidence_snippets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not evidence_snippets:
            return []

        required_skills = [
            str(skill.get("label") or skill.get("key") or "").strip()
            for skill in (competency_map.get("required_skills") or [])
            if isinstance(skill, dict) and str(skill.get("label") or skill.get("key") or "").strip()
        ]
        query_text = " ".join(
            [
                str(vacancy.title or ""),
                str(vacancy.company or ""),
                " ".join(required_skills),
                " ".join(str(item.get("message") or "") for item in (analysis.gaps_json or [])),
            ]
        )
        ranked = self.evidence_selection_service.rank_evidence(
            query_text=query_text,
            evidence_items=evidence_snippets,
            required_skills=required_skills,
            source_types=["achievement", "resume", "manual"],
            limit=8,
        )
        evidence_by_id = {
            str(item.get("id")): item
            for item in evidence_snippets
            if item.get("id")
        }
        ordered = [
            evidence_by_id[str(item.get("evidence_id"))]
            for item in ranked
            if str(item.get("evidence_id") or "") in evidence_by_id
        ]
        if ordered:
            return ordered
        return evidence_snippets

    async def list_sessions(self, session: AsyncSession, *, user_id: UUID) -> list[dict]:
        items = await self.prep_session_repository.list_by_user_id(
            session,
            user_id=user_id,
        )
        return [
            {
                "id": item.id,
                "application_id": item.application_id,
                "vacancy_id": item.vacancy_id,
                "prep_status": item.prep_status,
                "readiness_score": item.readiness_score,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in items
        ]

    async def get_session(
        self,
        session: AsyncSession,
        *,
        prep_session_id: UUID,
        user_id: UUID,
    ):
        prep_session = await self.prep_session_repository.get_by_id(
            session,
            prep_session_id,
            user_id=user_id,
        )
        if prep_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="interview prep session not found",
            )
        return prep_session

    def _achievement_to_dict(self, achievement) -> dict[str, Any]:
        return {
            "id": str(achievement.id),
            "title": achievement.title,
            "situation": achievement.situation,
            "task": achievement.task,
            "action": achievement.action,
            "result": achievement.result,
            "metric_text": achievement.metric_text,
            "evidence_note": achievement.evidence_note,
            "fact_status": achievement.fact_status,
        }

    def _evidence_snippet_to_dict(self, snippet) -> dict[str, Any]:
        return {
            "id": str(snippet.id),
            "user_id": str(snippet.user_id),
            "title": snippet.title,
            "snippet_text": snippet.snippet_text,
            "source_type": snippet.source_type,
            "skills": list(snippet.skills_json or []),
            "evidence_strength": snippet.evidence_strength,
            "fact_status": snippet.fact_status,
            "usage_count": snippet.usage_count,
            "used_in_documents_count": snippet.used_in_documents_count,
            "used_in_interviews_count": snippet.used_in_interviews_count,
            "star_summary": snippet.star_summary_json or {},
        }
