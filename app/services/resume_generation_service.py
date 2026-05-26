# app\services\resume_generation_service.py

from __future__ import annotations

import difflib
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.ai.orchestrator import AIOrchestrator

from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.domain.evidence import EvidenceSourceType
from app.domain.evidence_confidence import (
    aggregate_evidence_confidence,
)
from app.domain.document_models import SelectedAchievement
from app.services.document_compat import (
    achievement_to_dict,
    ensure_keyword_set,
    ensure_selected_achievement,
)
from app.services.document_feedback import build_claim, build_warning
from app.services.document_builders import build_resume_content
from app.services.evidence_bank_service import EVIDENCE_BANK_SOURCE_TYPES, EvidenceBankService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.evidence_selection_service import EvidenceSelectionService
from app.services.resume_renderer import render_resume


MAX_RESUME_WORDS = 1200
MAX_KEYWORD_LOSS_RATIO = 0.3

PROTECTED_TECH_TERMS = {
    "python",
    "fastapi",
    "postgresql",
    "redis",
    "docker",
    "kubernetes",
    "aws",
    "llm",
    "sqlalchemy",
}


class ResumeGenerationService:
    def __init__(
        self,
        vacancy_repository: VacancyRepository | None = None,
        vacancy_analysis_repository: VacancyAnalysisRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        evidence_snippet_repository: EvidenceSnippetRepository | None = None,
        file_extraction_repository: FileExtractionRepository | None = None,
        document_version_repository: DocumentVersionRepository | None = None,
        ai_orchestrator: AIOrchestrator | None = None,
        evidence_extraction_service: EvidenceExtractionService | None = None,
        evidence_selection_service: EvidenceSelectionService | None = None,
        evidence_bank_service: EvidenceBankService | None = None,
    ) -> None:
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.vacancy_analysis_repository = (
            vacancy_analysis_repository or VacancyAnalysisRepository()
        )
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.evidence_snippet_repository = (
            evidence_snippet_repository or EvidenceSnippetRepository()
        )
        self.file_extraction_repository = file_extraction_repository or FileExtractionRepository()
        self.document_version_repository = (
            document_version_repository or DocumentVersionRepository()
        )
        self.ai_orchestrator = ai_orchestrator
        self.evidence_extraction_service = (
            evidence_extraction_service or EvidenceExtractionService()
        )
        self.evidence_selection_service = (
            evidence_selection_service or EvidenceSelectionService()
        )
        self.evidence_bank_service = evidence_bank_service or EvidenceBankService(
            repository=self.evidence_snippet_repository,
            extraction_service=self.evidence_extraction_service,
        )

    async def generate_resume(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        user_id: UUID,
        use_ai_enhancement: bool = False,
    ):
        vacancy = await self.vacancy_repository.get_by_id(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        analysis = await self.vacancy_analysis_repository.get_latest_for_vacancy(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="vacancy analysis not found; run vacancy analysis first",
            )

        profile = await self.candidate_profile_repository.get_with_related_by_user_id(
            session,
            vacancy.user_id,
        )
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="candidate profile not found for vacancy user",
            )

        latest_extraction = await self.file_extraction_repository.get_latest_for_user(
            session,
            user_id,
        )

        raw_skills = self._extract_skills_from_profile_or_raw_text(
            profile_summary=profile.summary,
            raw_text=latest_extraction.extracted_text if latest_extraction else "",
        )

        keyword_set = ensure_keyword_set(self._extract_match_keywords_from_analysis(
            strengths_json=analysis.strengths_json,
            gaps_json=analysis.gaps_json,
        ))
        matched_keywords = keyword_set.matched
        missing_keywords = keyword_set.missing

        selected_skills = self._select_resume_skills(
            raw_skills=raw_skills,
            matched_keywords=matched_keywords,
        )

        confirmed_achievements = self._get_confirmed_achievements(profile.achievements)

        selected_achievements = self._select_relevant_achievements(
            confirmed_achievements,
            matched_keywords,
            user_id=str(vacancy.user_id),
        )

        evidence_bank = await self.evidence_bank_service.build_bank(
            session,
            user_id=vacancy.user_id,
            achievements=confirmed_achievements,
        )
        evidence_snippets = [item.as_dict() for item in evidence_bank.snippets]

        evidence_by_title = {
            re.sub(r"\s+", " ", str(snippet.get("title") or "").strip()).lower(): snippet
            for snippet in evidence_snippets
            if str(snippet.get("title") or "").strip() and str(snippet.get("id") or "").strip()
        }
        evidence_by_id = {
            str(snippet.get("id") or "").strip(): snippet
            for snippet in evidence_snippets
            if str(snippet.get("id") or "").strip()
        }

        selected_evidence_ids: list[str] = []
        selected_evidence_reason: list[dict[str, Any]] = []
        seen_selected_evidence_ids: set[str] = set()
        for item in selected_achievements:
            title_key = re.sub(r"\s+", " ", str(item.get("title") or "").strip()).lower()
            snippet = evidence_by_title.get(title_key)
            if snippet is None:
                continue

            evidence_id = str(snippet.get("id") or "").strip()
            if not evidence_id or evidence_id in seen_selected_evidence_ids:
                continue

            seen_selected_evidence_ids.add(evidence_id)
            selected_evidence_ids.append(evidence_id)
            selected_evidence_reason.append(
                {
                    "evidence_id": evidence_id,
                    "achievement_id": str(item.get("id") or "").strip() or None,
                    "title": str(item.get("title") or "").strip(),
                    "reason": str(item.get("reason") or "").strip() or "profile_core",
                    "fact_status": str(item.get("fact_status") or "").strip() or "confirmed",
                    "evidence_strength": str(snippet.get("evidence_strength") or "").strip() or None,
                }
            )

        if not selected_evidence_ids and evidence_snippets:
            fallback_ranked_evidence = self.evidence_selection_service.rank_evidence(
                query_text=" ".join(matched_keywords or missing_keywords),
                evidence_items=evidence_snippets,
                required_skills=matched_keywords or missing_keywords,
                source_types=EVIDENCE_BANK_SOURCE_TYPES,
                limit=3,
            )
            for item in fallback_ranked_evidence:
                evidence_id = str(item.get("evidence_id") or "").strip()
                if not evidence_id or evidence_id in seen_selected_evidence_ids:
                    continue

                snippet = evidence_by_id.get(evidence_id, {})
                seen_selected_evidence_ids.add(evidence_id)
                selected_evidence_ids.append(evidence_id)
                selected_evidence_reason.append(
                    {
                        "evidence_id": evidence_id,
                        "achievement_id": None,
                        "title": str(item.get("title") or snippet.get("title") or "").strip(),
                        "reason": str(item.get("reason") or "").strip() or "fallback evidence selection",
                        "fact_status": str(item.get("fact_status") or snippet.get("fact_status") or "").strip()
                        or None,
                        "evidence_strength": str(
                            item.get("evidence_strength") or snippet.get("evidence_strength") or ""
                        ).strip() or None,
                    }
                )

        if not selected_achievements and selected_evidence_ids:
            selected_achievements = self._selected_achievements_from_evidence_bank(
                selected_evidence_ids=selected_evidence_ids,
                evidence_by_id=evidence_by_id,
            )

        for snippet in evidence_snippets:
            snippet_id = str(snippet.get("id") or "")
            if snippet_id not in seen_selected_evidence_ids:
                continue
            try:
                await self.evidence_snippet_repository.record_usage(
                    session,
                    user_id=vacancy.user_id,
                    evidence_snippet_id=UUID(snippet_id),
                    usage_type="document",
                    target_type="resume",
                    target_id=str(vacancy.id),
                    note="resume generation",
                )
            except Exception:
                continue

        fit_summary = self._build_fit_summary(
            vacancy_title=vacancy.title,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            analysis_match_score=analysis.match_score,
        )
        tailoring = self._build_ats_tailoring_sections(
            vacancy_title=vacancy.title,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            evidence_snippets=evidence_snippets,
        )

        summary_bullets = self._build_summary_bullets(
            profile=profile,
            vacancy_title=vacancy.title,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            matched_keywords=matched_keywords,
        )

        experience_items = self._build_experience_items(profile)
        claims_needing_confirmation = self._build_claims_needing_confirmation(
            profile=profile,
            selected_achievements=selected_achievements,
        )
        selection_rationale = self._build_selection_rationale(
            selected_skills=selected_skills,
            matched_keywords=matched_keywords,
            selected_achievements=selected_achievements,
        )
        warnings = self._build_warnings(
            profile=profile,
            selected_achievements=selected_achievements,
            analysis_match_score=analysis.match_score,
            missing_keywords=missing_keywords,
        )

        # Опциональный AI-усиленный шаг
        if self.ai_orchestrator and use_ai_enhancement:
            from app.ai.use_cases.resume_tailoring import tailor_resume
            ai_result = await tailor_resume(
                self.ai_orchestrator,
                session,
                user_id=vacancy.user_id,
                vacancy=vacancy,
                analysis=analysis,
                profile=profile,
                achievements=selected_achievements,
            )
            # Если AI вернул улучшенный текст — можно применить к sections
            if ai_result and isinstance(ai_result, dict):
                ai_summary = ai_result.get("result", {}).get("summary")
                if ai_summary:
                    fit_summary = ai_summary

        confidence_assessment = self._build_confidence_assessment(
            selected_achievements=selected_achievements,
            selected_evidence_reason=selected_evidence_reason,
            missing_keywords=missing_keywords,
        )

        content_json = build_resume_content(
            candidate={
                "full_name": profile.full_name,
                "headline": profile.headline,
                "location": profile.location,
                "target_roles": profile.target_roles_json,
            },
            target_vacancy={
                "vacancy_id": str(vacancy.id),
                "title": vacancy.title,
                "company": vacancy.company,
                "location": vacancy.location,
            },
            draft_mode=(
                "ai_enhanced_v1" if use_ai_enhancement else "deterministic_v1_review_ready"
            ),
            fit_summary=fit_summary,
            vacancy_aligned_summary=tailoring["vacancy_aligned_summary"],
            competency_mapping=tailoring["competency_mapping"],
            relevant_to_vacancy=tailoring["relevant_to_vacancy"],
            summary_bullets=summary_bullets,
            skills=selected_skills,
            experience=experience_items,
            selected_achievements=selected_achievements,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            matched_requirements=analysis.strengths_json,
            gap_requirements=analysis.gaps_json,
            claims_needing_confirmation=claims_needing_confirmation,
            selection_rationale=selection_rationale,
            warnings=warnings,
            source="hybrid" if use_ai_enhancement else "extracted",
            based_on_achievements=[
                item["id"] for item in selected_achievements if item.get("id")
            ],
            selected_achievement_ids=[
                item["id"] for item in selected_achievements if item.get("id")
            ],
            based_on_analysis_id=str(analysis.id),
            selected_evidence_ids=selected_evidence_ids,
            evidence_selection_reason=selected_evidence_reason or selection_rationale,
            confidence=confidence_assessment.confidence,
            confidence_level=confidence_assessment.confidence_level.value,
            generation_prompt_version=(
                "resume_tailor_v1" if use_ai_enhancement else None
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        rendered_text = render_resume(content_json)

        document = await self.document_version_repository.create(
            session,
            user_id=vacancy.user_id,
            vacancy_id=vacancy.id,
            derived_from_id=None,
            analysis_id=analysis.id,
            document_kind="resume",
            version_label="resume_draft_v2_review_ready",
            review_status="draft",
            is_active=False,
            content_json=content_json,
            rendered_text=rendered_text,
        )

        await session.flush()
        await session.refresh(document)

        return document

    def _extract_skills_from_profile_or_raw_text(
        self,
        *,
        profile_summary: str | None,
        raw_text: str,
    ) -> list[str]:
        summary_skills = self._split_skill_text(profile_summary or "")
        if summary_skills:
            return summary_skills

        return self._extract_skills_from_raw_text(raw_text)

    def _split_skill_text(self, text: str) -> list[str]:
        if not text:
            return []

        parts = re.split(r"[,\n;]+", text)
        cleaned_parts = [
            cleaned
            for part in parts
            if (cleaned := self._clean_skill_candidate(part))
        ]
        return self._dedupe_preserve_order(cleaned_parts)

    def _clean_skill_candidate(self, value: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", value.strip(" .;-–—•"))
        if not cleaned:
            return None

        noise_markers = [
            "Прошел",
            "Прошёл",
            "направлению",
            "Желаемая должность",
            "ОПЫТ РАБОТЫ",
            "ОБРАЗОВАНИЕ",
        ]

        for marker in noise_markers:
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[0].strip(" .;-–—•")

        if not cleaned:
            return None

        if len(cleaned) > 80:
            return None

        return cleaned

    def _extract_match_keywords_from_analysis(
        self,
        *,
        strengths_json: list[dict],
        gaps_json: list[dict],
    ) -> tuple[list[str], list[str]]:
        matched_keywords = self._dedupe_preserve_order(
            [
                item.get("keyword", "")
                for item in strengths_json or []
                if item.get("keyword")
            ]
        )
        missing_keywords = self._dedupe_preserve_order(
            [
                item.get("keyword", "")
                for item in gaps_json or []
                if item.get("keyword")
            ]
        )
        return matched_keywords, missing_keywords

    def _extract_skills_from_raw_text(self, text: str) -> list[str]:
        if not text:
            return []

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        capture = False
        section_lines: list[str] = []

        for line in lines:
            normalized = line.upper()

            if normalized == "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ":
                capture = True
                continue

            if capture and normalized in {
                "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
                "ОПЫТ РАБОТЫ",
                "ОБРАЗОВАНИЕ",
            }:
                break

            if capture:
                section_lines.append(line)

        if not section_lines:
            return []

        joined = " ".join(section_lines)
        parts = [
            cleaned
            for part in joined.split(",")
            if (cleaned := self._clean_skill_candidate(part))
        ]
        return self._dedupe_preserve_order(parts)

    def _select_resume_skills(
        self,
        *,
        raw_skills: list[str],
        matched_keywords: list[str],
    ) -> list[str]:
        matched_skills: list[str] = []

        for keyword in matched_keywords:
            for raw_skill in raw_skills:
                if self._skill_matches_keyword(raw_skill, keyword):
                    matched_skills.append(raw_skill)

        matched_skills = self._dedupe_preserve_order(matched_skills)
        remaining = [skill for skill in raw_skills if skill not in matched_skills]
        return (matched_skills + remaining)[:12]

    def _skill_matches_keyword(self, raw_skill: str, keyword: str) -> bool:
        raw = raw_skill.strip().lower()
        key = keyword.strip().lower()

        if not raw or not key:
            return False

        if raw == key:
            return True

        # Specific skill can satisfy generic requirement in resume selection,
        # but not the opposite.
        generic_satisfied_by_specific = {
            "api": {"fastapi"},
            "sql": {"postgresql", "postgres"},
            "automation": {"ai workflow", "no-code", "nocode", "low-code"},
            "llm": {"chatgpt", "gpt-4", "gpt4", "claude"},
            "ai interaction": {"prompt engineering", "chatgpt", "llm"},
        }

        specific_satisfied_by_generic = {
            "ai workflow": {"automation"},
            "no-code": {"automation", "automation tooling"},
            "prompt engineering": {"ai interaction", "llm tooling"},
            "chatgpt": {"llm", "llm tooling"},
        }

        return (
            raw in generic_satisfied_by_specific.get(key, set())
            or raw in specific_satisfied_by_generic.get(key, set())
        )

    def _get_confirmed_achievements(self, achievements) -> list[dict]:
        items: list[dict] = []

        for achievement in achievements or []:
            title = str(getattr(achievement, "title", "") or "").strip()
            fact_status = str(getattr(achievement, "fact_status", "") or "").strip()

            if not title or fact_status != "confirmed":
                continue

            items.append(
                {
                    "id": str(getattr(achievement, "id", "")),
                    "title": title,
                    "situation": getattr(achievement, "situation", None),
                    "task": getattr(achievement, "task", None),
                    "action": getattr(achievement, "action", None),
                    "result": getattr(achievement, "result", None),
                    "metric_text": getattr(achievement, "metric_text", None),
                    "fact_status": "confirmed",
                }
            )

        deduped: list[dict] = []
        seen: set[str] = set()

        for item in items:
            normalized = re.sub(r"\s+", " ", item["title"].strip()).lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(item)

        return deduped

    def _get_confirmed_achievement_titles(self, achievements) -> list[str]:
        """
        Backward-compatible helper for existing tests and simple title-only flows.
        Main generation path uses _get_confirmed_achievements().
        """
        return [
            item["title"]
            for item in self._get_confirmed_achievements(achievements)
        ]

    def _evidence_snippet_to_dict(self, snippet) -> dict:
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

    def _select_relevant_achievements(
        self,
        achievements: list[dict],
        keywords: list[str],
        *,
        user_id: str | None = None,
    ) -> list[dict]:
        ordered_achievements = achievements
        if user_id:
            evidence_items = [
                self.evidence_extraction_service.extract_from_achievement(
                    achievement,
                    user_id=user_id,
                    source_type=EvidenceSourceType.ACHIEVEMENT,
                ).as_dict()
                for achievement in achievements
            ]
            ranked_evidence = self.evidence_selection_service.rank_evidence(
                query_text=" ".join(keywords),
                evidence_items=evidence_items,
                required_skills=keywords,
                source_types=["achievement"],
                limit=3,
            )
            achievement_by_id = {
                str(achievement.get("id")): achievement
                for achievement in achievements
                if achievement.get("id")
            }
            ordered_achievements = [
                achievement_by_id[str(item.get("achievement_id"))]
                for item in ranked_evidence
                if str(item.get("achievement_id") or "") in achievement_by_id
            ] or achievements

        selected: list[SelectedAchievement] = []

        for achievement in ordered_achievements:
            title = str(achievement.get("title") or "").strip()
            if not title:
                continue

            reason = "profile_core"
            title_lower = title.lower()

            if any(keyword.lower() in title_lower for keyword in keywords):
                reason = "keyword_overlap"
            elif "ии" in title_lower or "ai" in title_lower:
                reason = "ai_relevance"
            elif "анализ" in title_lower or "data" in title_lower:
                reason = "analysis_relevance"

            selected.append(
                SelectedAchievement(
                    id=achievement.get("id"),
                    title=title,
                    situation=achievement.get("situation"),
                    task=achievement.get("task"),
                    action=achievement.get("action"),
                    result=achievement.get("result"),
                    metric_text=achievement.get("metric_text"),
                    fact_status="confirmed",
                    reason=reason,
                )
            )

        selected = sorted(
            selected,
            key=lambda item: (
                0 if item.reason == "keyword_overlap" else
                1 if item.reason == "ai_relevance" else
                2 if item.reason == "analysis_relevance" else
                3
            ),
        )
        return [
            achievement_to_dict(item)
            for item in selected[:3]
        ]

    def _selected_achievements_from_evidence_bank(
        self,
        *,
        selected_evidence_ids: list[str],
        evidence_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for evidence_id in selected_evidence_ids:
            snippet = evidence_by_id.get(evidence_id)
            if not snippet:
                continue
            category = str((snippet.get("star_summary") or {}).get("category") or "")
            if category not in {
                "project",
                "ai_project",
                "automation",
                "prompt_engineering",
                "internship",
                "achievement",
            }:
                continue
            selected.append(
                {
                    "id": evidence_id,
                    "title": str(snippet.get("title") or "Evidence").strip(),
                    "situation": None,
                    "task": None,
                    "action": str(snippet.get("snippet_text") or "").strip() or None,
                    "result": None,
                    "metric_text": None,
                    "fact_status": str(snippet.get("fact_status") or "user_provided"),
                    "reason": "evidence_bank_project",
                }
            )
            if len(selected) >= 3:
                break
        return selected

    def _build_fit_summary(
        self,
        *,
        vacancy_title: str,
        matched_keywords: list[str],
        missing_keywords: list[str],
        analysis_match_score: int | None,
    ) -> dict:
        return {
            "target_role": vacancy_title,
            "match_score": analysis_match_score,
            "matched_keyword_count": len(matched_keywords),
            "missing_keyword_count": len(missing_keywords),
        }

    def _build_summary_bullets(
        self,
        *,
        profile,
        vacancy_title: str,
        selected_skills: list[str],
        selected_achievements: list[dict],
        matched_keywords: list[str],
    ) -> list[str]:
        bullets: list[str] = []

        if profile.headline:
            bullets.append(f"Профессиональный фокус: {profile.headline}.")

        if matched_keywords:
            bullets.append(
                f"Подтверждённые пересечения с вакансией {vacancy_title}: "
                f"{', '.join(matched_keywords[:6])}."
            )

        if selected_skills:
            bullets.append(
                f"Дополнительные навыки из резюме: {', '.join(selected_skills[:8])}."
            )

        if selected_achievements:
            bullets.append(
                "Проектный опыт для проверки и возможного использования в отклике: "
                f"{ensure_selected_achievement(selected_achievements[0]).title}."
            )

        return bullets[:4]

    def _build_ats_tailoring_sections(
        self,
        *,
        vacancy_title: str,
        matched_keywords: list[str],
        missing_keywords: list[str],
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
        evidence_snippets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        relevant_to_vacancy = self._build_relevant_to_vacancy(
            matched_keywords=matched_keywords,
            selected_skills=selected_skills,
            evidence_snippets=evidence_snippets,
        )
        vacancy_aligned_summary = self._build_vacancy_aligned_summary(
            vacancy_title=vacancy_title,
            relevant_to_vacancy=relevant_to_vacancy,
            selected_achievements=selected_achievements,
        )
        competency_mapping = self._build_competency_mapping(
            relevant_to_vacancy=relevant_to_vacancy,
            evidence_snippets=evidence_snippets,
            missing_keywords=missing_keywords,
        )
        return {
            "vacancy_aligned_summary": vacancy_aligned_summary,
            "competency_mapping": competency_mapping,
            "relevant_to_vacancy": relevant_to_vacancy,
        }

    def _build_vacancy_aligned_summary(
        self,
        *,
        vacancy_title: str,
        relevant_to_vacancy: list[str],
        selected_achievements: list[dict[str, Any]],
    ) -> str:
        role = vacancy_title.strip() or "Target role"
        focus_terms = relevant_to_vacancy[:4]
        if not focus_terms:
            focus_terms = [
                str(item.get("title") or "").strip()
                for item in selected_achievements[:2]
                if str(item.get("title") or "").strip()
            ]
        focus = ", ".join(focus_terms) if focus_terms else "role-relevant delivery"
        return (
            f"{role} candidate with hands-on experience in {focus}, "
            "grounded in extracted resume evidence and tailored to the vacancy requirements."
        )

    def _build_relevant_to_vacancy(
        self,
        *,
        matched_keywords: list[str],
        selected_skills: list[str],
        evidence_snippets: list[dict[str, Any]],
    ) -> list[str]:
        candidates: list[str] = []

        for keyword in matched_keywords:
            normalized = keyword.strip()
            if normalized:
                candidates.append(self._display_relevance_label(normalized))

        evidence_text = " ".join(
            [
                " ".join(str(skill) for skill in snippet.get("skills") or [])
                + " "
                + str(snippet.get("title") or "")
                + " "
                + str(snippet.get("snippet_text") or "")
                for snippet in evidence_snippets
            ]
        ).lower()
        semantic_rules = [
            ("Prompt engineering", ("prompt", "prompt engineering", "промпт")),
            ("AI tooling", ("llm", "chatgpt", "ai interaction", "ai tooling")),
            ("Workflow automation", ("automation", "workflow", "no-code", "nocode")),
            ("Python-based AI systems", ("python", "ai", "llm")),
        ]
        for label, markers in semantic_rules:
            if any(marker in evidence_text for marker in markers):
                candidates.append(label)

        for skill in selected_skills:
            if skill:
                candidates.append(self._display_relevance_label(skill))

        return self._dedupe_preserve_order(candidates)[:8]

    def _build_competency_mapping(
        self,
        *,
        relevant_to_vacancy: list[str],
        evidence_snippets: list[dict[str, Any]],
        missing_keywords: list[str],
    ) -> list[dict[str, Any]]:
        mapping: list[dict[str, Any]] = []
        for competency in relevant_to_vacancy[:6]:
            evidence = self._find_best_evidence_for_competency(
                competency,
                evidence_snippets,
            )
            mapping.append(
                {
                    "competency": competency,
                    "coverage": "supported" if evidence else "profile_keyword",
                    "evidence_id": evidence.get("id") if evidence else None,
                    "evidence_title": evidence.get("title") if evidence else None,
                    "evidence": evidence.get("title") if evidence else "Matched profile keyword",
                    "fact_status": evidence.get("fact_status") if evidence else "needs_review",
                }
            )

        for keyword in missing_keywords[:3]:
            if not keyword:
                continue
            mapping.append(
                {
                    "competency": self._display_relevance_label(keyword),
                    "coverage": "gap",
                    "evidence_id": None,
                    "evidence_title": None,
                    "evidence": "No strong extracted evidence yet",
                    "fact_status": "needs_review",
                }
            )

        return mapping[:8]

    def _find_best_evidence_for_competency(
        self,
        competency: str,
        evidence_snippets: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        competency_tokens = {
            token
            for token in re.split(r"[^a-z0-9а-яё]+", competency.lower())
            if len(token) >= 3
        }
        best: tuple[int, dict[str, Any]] | None = None
        for snippet in evidence_snippets:
            text = " ".join(
                [
                    str(snippet.get("title") or ""),
                    str(snippet.get("snippet_text") or ""),
                    " ".join(str(skill) for skill in snippet.get("skills") or []),
                ]
            ).lower()
            score = sum(1 for token in competency_tokens if token in text)
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, snippet)
        return best[1] if best else None

    def _display_relevance_label(self, value: str) -> str:
        normalized = value.strip().replace("_", " ")
        known = {
            "llm": "AI tooling",
            "chatgpt": "AI tooling",
            "prompt engineering": "Prompt engineering",
            "ai interaction": "AI interaction",
            "ai workflow": "Workflow automation",
            "automation": "Workflow automation",
            "automation tooling": "Workflow automation",
            "no-code": "Workflow automation",
            "python": "Python-based AI systems",
        }
        return known.get(normalized.lower(), normalized)

    def _build_experience_items(self, profile) -> list[dict]:
        items: list[dict] = []

        for exp in profile.experiences[:5]:
            item = {
                "company": exp.company,
                "role": exp.role,
                "period": self._format_period(exp.start_date, exp.end_date),
                "description_raw": exp.description_raw,
            }

            if self._looks_like_low_confidence_experience_item(item):
                continue

            items.append(item)

        return items

    def _looks_like_low_confidence_experience_item(self, item: dict) -> bool:
        combined = " ".join(
            str(item.get(field) or "")
            for field in ("company", "role", "description_raw")
        )
        normalized = combined.lower()
        # Оставляем только явный шум от PDF-парсера
        noise_patterns = [
            r"\b\d+\.\s+",  # нумерация вместо названия
            r"ии-контроль",
            r"пвх оконных",
            r"по изображениям",
            r"видео layout noise",
        ]
        return any(re.search(pattern, normalized) for pattern in noise_patterns)

    def _build_claims_needing_confirmation(
        self,
        *,
        profile,
        selected_achievements: list[dict],
    ) -> list[dict]:
        claims: list[dict] = []

        for item in selected_achievements:
            achievement = ensure_selected_achievement(item)
            if achievement.fact_status == "confirmed":
                continue

            claims.append(
                build_claim(
                    claim_type="achievement",
                    text=achievement.title,
                    fact_status=achievement.fact_status,
                    source="candidate_achievements",
                )
            )

        if not profile.full_name:
            claims.append(
                build_claim(
                    claim_type="profile_field",
                    text="full_name missing",
                    fact_status="needs_confirmation",
                    source="candidate_profile",
                )
            )

        return claims

    def _build_selection_rationale(
        self,
        *,
        selected_skills: list[str],
        matched_keywords: list[str],
        selected_achievements: list[dict],
    ) -> list[dict]:
        rationale: list[dict] = []

        for skill in selected_skills[:6]:
            reason = "resume_skill"
            if any(keyword.lower() in skill.lower() or skill.lower() in keyword.lower() for keyword in matched_keywords):
                reason = "vacancy_overlap"
            rationale.append({"item": skill, "type": "skill", "reason": reason})

        for ach in selected_achievements:
            achievement = ensure_selected_achievement(ach)
            rationale.append(
                {
                    "item": achievement.title,
                    "type": "achievement",
                    "reason": achievement.reason,
                }
            )

        return rationale

    def _build_warnings(
        self,
        *,
        profile,
        selected_achievements: list[dict],
        analysis_match_score: int | None,
        missing_keywords: list[str],
    ) -> list[dict]:
        warnings: list[dict] = []

        if any(ensure_selected_achievement(item).fact_status != "confirmed" for item in selected_achievements):
            warnings.append(
                build_warning(
                    code="unconfirmed_achievements",
                    message=(
                        "selected achievements remain in needs_confirmation status "
                        "and require user review"
                    ),
                    severity="warning",
                )
            )

        if analysis_match_score is not None and analysis_match_score < 40:
            warnings.append(
                build_warning(
                    code="low_match_score",
                    message=(
                        "vacancy match score is currently low because structured "
                        "profile coverage is still limited"
                    ),
                    severity="warning",
                )
            )

        if missing_keywords:
            warnings.append(
                build_warning(
                    code="missing_vacancy_keywords",
                    message=(
                        "missing or weakly represented vacancy keywords: "
                        f"{', '.join(missing_keywords[:6])}"
                    ),
                    severity="warning",
                )
            )

        warnings.append(
            build_warning(
                code="ats_plaintext_draft",
                message=(
                    "resume draft is ATS-safe plaintext-oriented and not final "
                    "formatted output"
                ),
                severity="info",
            )
        )
        return warnings

    def _build_confidence_assessment(
        self,
        *,
        selected_achievements: list[dict],
        selected_evidence_reason: list[dict[str, Any]] | None = None,
        missing_keywords: list[str],
    ):
        """Deterministically normalize confidence for resume drafts."""
        evidence_items = selected_evidence_reason or selected_achievements
        assessment = aggregate_evidence_confidence(
            [
                self._confidence_item_from_achievement(item)
                if "evidence_id" not in item
                else item
                for item in evidence_items
            ],
        )
        if missing_keywords:
            penalty = min(len(missing_keywords) * 0.03, 0.2)
            assessment.confidence = round(max(0.1, assessment.confidence - penalty), 2)
            if assessment.confidence_level.value == "high" and assessment.confidence < 0.8:
                assessment.confidence_level = assessment.confidence_level.__class__.MEDIUM
        return assessment

    def _compute_confidence(
        self,
        *,
        selected_achievements: list[dict],
        missing_keywords: list[str],
    ) -> float:
        return self._build_confidence_assessment(
            selected_achievements=selected_achievements,
            missing_keywords=missing_keywords,
        ).confidence

    def _confidence_item_from_achievement(self, achievement: dict[str, Any]) -> dict[str, Any]:
        item = ensure_selected_achievement(achievement)
        return {
            "id": item.id,
            "title": item.title,
            "fact_status": item.fact_status,
            "evidence_strength": (
                "strong"
                if item.fact_status == "confirmed" and item.metric_text
                else "medium"
                if item.fact_status == "confirmed"
                else "weak"
            ),
            "star_summary": {
                "situation": item.situation,
                "task": item.task,
                "action": item.action,
                "result": item.result,
            },
        }

    def _format_period(self, start_date, end_date) -> str:
        start = start_date.strftime("%m.%Y") if start_date else "не указано"
        end = end_date.strftime("%m.%Y") if end_date else "н.в."
        return f"{start} - {end}"

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for value in values:
            normalized = re.sub(r"\s+", " ", value.strip()).lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(value.strip())

        return result

    async def enhance_resume_with_ai(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        resume_text: str,
        language: str = "ru",
    ) -> str:
        if not self.ai_orchestrator:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI orchestrator not configured",
            )

        from app.ai.use_cases.resume_enhance import enhance_resume

        result = await enhance_resume(
            self.ai_orchestrator,
            session,
            user_id=user_id,
            resume_text=resume_text,
            language=language,
        )

        enhanced = result["result"]["enhanced_text"]

        if not self._is_safe_enhancement(resume_text, enhanced):
            # fallback → возвращаем оригинал
            return resume_text

        return enhanced

    def _compute_diff(self, original: str, enhanced: str) -> str:
        diff = difflib.unified_diff(
            original.splitlines(),
            enhanced.splitlines(),
            lineterm="",
        )
        return "\n".join(diff)

    def _word_count(self, text: str) -> int:
        return len(text.split())

    def _normalize_text_tokens(self, text: str) -> set[str]:
        normalized = re.sub(r"[^\w\s]", " ", text.lower())

        tokens = {
            token.strip()
            for token in normalized.split()
            if len(token.strip()) >= 4
        }

        stopwords = {
            "with",
            "from",
            "that",
            "this",
            "using",
            "implemented",
            "system",
            "built",
        }

        return {
            token
            for token in tokens
            if token not in stopwords
        }

    def _is_safe_enhancement(self, original: str, enhanced: str) -> bool:
        orig_words = self._word_count(original)
        enh_words = self._word_count(enhanced)

        if enh_words == 0:
            return False

        if enh_words < orig_words * 0.5:
            return False

        if enh_words > min(orig_words * 2.5, MAX_RESUME_WORDS):
            return False

        original_tokens = self._normalize_text_tokens(original)
        enhanced_tokens = self._normalize_text_tokens(enhanced)

        if not original_tokens:
            return True

        retained = original_tokens.intersection(enhanced_tokens)
        retention_ratio = len(retained) / len(original_tokens)

        if retention_ratio < (1 - MAX_KEYWORD_LOSS_RATIO):
            return False

        original_lower = original.lower()
        enhanced_lower = enhanced.lower()

        protected_terms = {
            term
            for term in PROTECTED_TECH_TERMS
            if term in original_lower
        }

        for term in protected_terms:
            if term not in enhanced_lower:
                return False

        return True
