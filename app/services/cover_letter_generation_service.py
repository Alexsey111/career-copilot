# app\services\cover_letter_generation_service.py

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.ai.orchestrator import AIOrchestrator

from app.db.session import AsyncSessionLocal
from app.domain.document_models import GapMitigation, SelectedAchievement
from app.domain.evidence import EvidenceSourceType
from app.domain.evidence_confidence import aggregate_evidence_confidence
from app.models import Vacancy
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.document_version_repository import DocumentVersionRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.services.document_builders import build_cover_letter_content
from app.services.document_compat import (
    achievement_to_dict,
    ensure_keyword_set,
    ensure_selected_achievement,
)
from app.services.document_feedback import build_claim, build_warning
from app.services.evidence_bank_service import EvidenceBankService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.evidence_selection_service import EvidenceSelectionService
from app.services.document_evidence_selection_service import DocumentEvidenceSelectionService
from app.services.vacancy_fit_context_service import VacancyFitContextService
from app.domain.evidence_alignment import (
    humanize_experience_phrase,
    score_alignment_item,
)
from app.domain.requirement_normalization import (
    classify_requirement_phrase,
    normalize_requirement_phrase,
    requirement_match_key,
)
from app.domain.text_normalization import (
    clean_vacancy_title,
    dedupe_subsumed_phrases,
    make_user_facing_evidence_phrase,
)
from app.services.resume_renderer import render_cover_letter
from app.services.core_service_policy import LEGACY_CANDIDATE_SPECIFIC_HEURISTIC
from app.services.text_polish.achievement_verbalizer import AchievementVerbalizer
from app.services.text_polish.humanizer import (
    CoverLetterHumanizer,
)
from app.services.text_polish.narrative_builder import NarrativeBuilder

logger = logging.getLogger(__name__)
LEGACY_DOMAIN_SPECIFIC_SYNTHESIS = LEGACY_CANDIDATE_SPECIFIC_HEURISTIC

LOW_SIGNAL_SKILLS = {
    "html",
    "mako",
    "dockerfile",
    "powershell",
    "пользователь пк",
}

KNOWN_PROFILE_SKILLS = (
    "Adobe Photoshop",
    "Adobe Illustrator",
    "Figma",
    "CorelDRAW",
)

PROJECT_DISPLAY_HINTS = {
    "content-factory": "automation workflow evidence",
    "career-copilot": "backend workflow evidence",
}

SOFT_COMPETENCIES = {
    "аккуратность",
    "внимательность",
    "ответственность",
    "исполнительность",
    "коммуникабельность",
}

BUSINESS_MANAGEMENT_MARKERS = {
    "закуп",
    r"(?<!водо)снабжен",
    "мто",
    "поставщик",
    "бюджет",
    "логист",
}


class CoverLetterGenerationService:
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
        self.cover_letter_humanizer = CoverLetterHumanizer()
        self.document_evidence_selection_service = DocumentEvidenceSelectionService()
        self.achievement_verbalizer = AchievementVerbalizer()
        self.narrative_builder = NarrativeBuilder()

    async def generate_cover_letter(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        user_id: UUID,
        use_ai_enhancement: bool = False,
    ):
        vacancy = await session.get(Vacancy, vacancy_id)
        if vacancy is None or vacancy.user_id != user_id:
            vacancy = await self._load_vacancy_fallback(vacancy_id=vacancy_id)

        if vacancy is None or vacancy.user_id != user_id:
            logger.warning(
                "cover_letter_vacancy_lookup_failed",
                extra={
                    "vacancy_id": str(vacancy_id),
                    "user_id": str(user_id),
                },
            )
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

        vacancy_title = clean_vacancy_title(vacancy.title)

        latest_extraction = await self.file_extraction_repository.get_latest_for_active_source_file_kind(
            session,
            user_id,
            file_kind="resume",
        )
        contact_info = self._extract_contact_info(
            latest_extraction.extracted_text if latest_extraction else ""
        )

        keyword_set = ensure_keyword_set(self._extract_match_keywords_from_analysis(
            strengths_json=analysis.strengths_json,
            gaps_json=analysis.gaps_json,
        ))
        matched_keywords = keyword_set.matched
        missing_keywords = keyword_set.missing

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
        evidence_snippets = self._filter_document_usable_evidence(evidence_snippets)

        evidence_by_title = {
            re.sub(r"\s+", " ", str(snippet.get("title") or "").strip()).lower(): snippet
            for snippet in evidence_snippets
            if str(snippet.get("title") or "").strip() and str(snippet.get("id") or "").strip()
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
                    "fact_status": str(
                        snippet.get("fact_status") or item.get("fact_status") or ""
                    ).strip() or "confirmed",
                    "evidence_strength": str(snippet.get("evidence_strength") or "").strip() or None,
                }
            )

        selected_cover_letter_evidence = self._select_cover_letter_evidence(
            vacancy_title=vacancy_title,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            evidence_snippets=evidence_snippets,
        )
        for item in selected_cover_letter_evidence:
            evidence_id = str(item.get("evidence_id") or "").strip()
            if not evidence_id or evidence_id in seen_selected_evidence_ids:
                continue

            seen_selected_evidence_ids.add(evidence_id)
            selected_evidence_ids.append(evidence_id)
            selected_evidence_reason.append(
                {
                    "evidence_id": evidence_id,
                    "achievement_id": None,
                    "title": str(item.get("title") or "").strip(),
                    "reason": str(item.get("reason") or "").strip() or "vacancy relevance evidence",
                    "source_type": str(item.get("source_type") or "").strip() or None,
                    "fact_status": str(item.get("fact_status") or "").strip() or None,
                    "evidence_strength": str(item.get("evidence_strength") or "").strip() or None,
                    "skills": list(item.get("skills") or []),
                }
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
                    target_type="cover_letter",
                    target_id=str(vacancy.id),
                    note="cover letter generation",
                )
            except Exception:
                continue

        # Собираем профильные навыки для контекста
        profile_skills = self._extract_skills_from_profile(profile)
        vacancy_fit_context = VacancyFitContextService().build(
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            selected_skills=profile_skills,
            evidence_snippets=evidence_snippets,
            selected_achievements=selected_achievements,
        )
        vacancy_evidence_alignment = vacancy_fit_context["vacancy_evidence_alignment"]
        document_evidence_selection = (
            self.document_evidence_selection_service.build_from_document_parts(
                selected_achievements=selected_achievements,
                selected_evidence_ids=selected_evidence_ids,
                evidence_selection_reason=selected_evidence_reason,
                vacancy_evidence_alignment=vacancy_evidence_alignment,
                top_alignment_evidence=[],
            )
        )
        vacancy_fit_narrative = vacancy_fit_context["vacancy_fit_narrative"]

        opening = self._build_opening(
            full_name=profile.full_name,
            vacancy_title=vacancy_title,
            company=vacancy.company,
            headline=profile.headline,
        )
        relevance_paragraph = self._build_relevance_paragraph(
            matched_keywords=matched_keywords,
            selected_achievements=selected_achievements,
            selected_evidence=selected_cover_letter_evidence,
            missing_keywords=missing_keywords,
            profile_skills=profile_skills,
            vacancy_title=vacancy_title,
            candidate_experiences=profile.experiences,
            vacancy_fit_narrative=vacancy_fit_narrative,
        )
        vacancy_alignment = vacancy_evidence_alignment
        evidence_relevance = self._build_evidence_relevance(
            selected_evidence=selected_cover_letter_evidence,
            selected_achievements=selected_achievements,
        )
        closing = self._build_closing(
            vacancy_title=vacancy_title,
            company=vacancy.company,
            candidate_experiences=profile.experiences,
            selected_skills=profile_skills,
            matched_keywords=matched_keywords,
            selected_achievements=selected_achievements,
        )
        polished_sections = self.cover_letter_humanizer.polish_sections(
            opening=opening,
            relevance_paragraph=relevance_paragraph,
            closing=closing,
        )
        opening = polished_sections["opening"]
        relevance_paragraph = polished_sections["relevance_paragraph"]
        closing = polished_sections["closing"]
        claims_needing_confirmation = self._build_claims_needing_confirmation(
            selected_achievements=selected_achievements,
        )
        selection_rationale = self._build_selection_rationale(
            matched_keywords=matched_keywords,
            selected_achievements=selected_achievements,
        )
        warnings = self._build_warnings(
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            selected_achievements=selected_achievements,
            selected_evidence_reason=selected_evidence_reason,
        )

        # Опциональный AI-усиленный шаг для всего письма
        rendered_text = render_cover_letter(
            {
                "sections": {
                    "opening": opening,
                    "relevance_paragraph": relevance_paragraph,
                    "closing": closing,
                    "vacancy_alignment": vacancy_alignment,
                    "evidence_relevance": evidence_relevance,
                    "warnings": warnings,
                }
            }
        )

        if use_ai_enhancement and self.ai_orchestrator:
            from app.ai.use_cases.cover_letter_enhance import enhance_cover_letter

            enhanced = await enhance_cover_letter(
                self.ai_orchestrator,
                session,
                user_id=user_id,
                draft_text=rendered_text,
                language="ru",
            )

            enhanced_text = enhanced["result"]["enhanced_text"]

            if not self._is_safe_enhancement(rendered_text, enhanced_text):
                rendered_text = rendered_text  # fallback, не меняем
            else:
                rendered_text = enhanced_text

        confidence_assessment = self._build_confidence_assessment(
            selected_achievements=selected_achievements,
            selected_evidence_reason=selected_evidence_reason,
            missing_keywords=missing_keywords,
        )

        content_json = build_cover_letter_content(
            candidate={
                "full_name": profile.full_name,
                "headline": profile.headline,
                "location": profile.location,
                "contacts": contact_info,
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
            opening=opening,
            relevance_paragraph=relevance_paragraph,
            closing=closing,
            vacancy_alignment=vacancy_alignment,
            evidence_relevance=evidence_relevance,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            matched_requirements=analysis.strengths_json,
            gap_requirements=analysis.gaps_json,
            selected_achievements=document_evidence_selection.selected_achievements,
            claims_needing_confirmation=claims_needing_confirmation,
            warnings=warnings,
            source="hybrid" if use_ai_enhancement else "extracted",
            based_on_achievements=[
                item.get("id")
                for item in document_evidence_selection.selected_achievements
                if item.get("id")
            ],
            selected_achievement_ids=[
                item.get("id")
                for item in document_evidence_selection.selected_achievements
                if item.get("id")
            ],
            based_on_analysis_id=str(analysis.id),
            selected_evidence_ids=document_evidence_selection.selected_evidence_ids,
            evidence_selection_reason=document_evidence_selection.evidence_selection_reason,
            confidence=confidence_assessment.confidence,
            confidence_level=confidence_assessment.confidence_level.value,
            generation_prompt_version=(
                "cover_letter_v1" if use_ai_enhancement else None
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        document = await self.document_version_repository.create(
            session,
            user_id=vacancy.user_id,
            vacancy_id=vacancy.id,
            derived_from_id=None,
            analysis_id=analysis.id,
            document_kind="cover_letter",
            version_label="cover_letter_draft_v1" if not use_ai_enhancement else "cover_letter_ai_enhanced_v1",
            review_status="draft",
            is_active=False,
            content_json=content_json,
            rendered_text=rendered_text,
        )

        await session.flush()
        await session.refresh(document)

        return document

    async def _load_vacancy_fallback(self, *, vacancy_id: UUID) -> Vacancy | None:
        async with AsyncSessionLocal() as lookup_session:
            return await lookup_session.get(Vacancy, vacancy_id)

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
        parts = [part.strip(" .") for part in joined.split(",") if part.strip()]
        return self._dedupe_preserve_order(parts)

    def _split_skill_text(self, text: str) -> list[str]:
        if not text:
            return []
        extracted = [
            skill
            for skill in KNOWN_PROFILE_SKILLS
            if re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", text, re.IGNORECASE)
        ]
        parts = re.split(r"[,\n;]+", text)
        cleaned = [
            re.sub(r"\s+", " ", part.strip(" .;-–—•"))
            for part in parts
            if part.strip(" .;-–—•")
        ]
        return self._dedupe_preserve_order([*extracted, *cleaned])

    def _extract_skills_from_profile(self, profile) -> list[str]:
        """Извлекает список навыков из профиля для контекста gap-mitigation"""
        skills: list[str] = []
        # Из headline и summary
        if profile.headline:
            skills.extend(self._split_skill_text(profile.headline))
        if profile.summary:
            skills.extend(self._split_skill_text(profile.summary))
        # Из опыта работы
        for exp in profile.experiences or []:
            if exp.description_raw:
                skills.extend(self._extract_skills_from_raw_text(exp.description_raw))
        # Из достижений
        for ach in profile.achievements or []:
            if getattr(ach, "title", None):
                skills.extend(self._split_skill_text(ach.title))
            if ach.action:
                skills.extend(self._split_skill_text(ach.action))
            if ach.result:
                skills.extend(self._split_skill_text(ach.result))
            for skill in getattr(ach, "skills_json", None) or []:
                skills.extend(self._split_skill_text(str(skill)))
        return self._dedupe_preserve_order(skills)

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
        achievements: list[dict] | None = None,
        keywords: list[str] | None = None,
        achievement_titles: list[str] | None = None,
        *,
        user_id: str | None = None,
    ) -> list[dict]:
        keywords = keywords or []
        legacy_title_only_mode = achievements is None

        if achievements is None:
            achievements = [
                {
                    "title": title,
                    "fact_status": "confirmed",
                }
                for title in (achievement_titles or [])
            ]

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
                limit=2,
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
                    situation=None if legacy_title_only_mode else achievement.get("situation"),
                    task=None if legacy_title_only_mode else achievement.get("task"),
                    action=None if legacy_title_only_mode else achievement.get("action"),
                    result=None if legacy_title_only_mode else achievement.get("result"),
                    metric_text=None if legacy_title_only_mode else achievement.get("metric_text"),
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
            for item in selected[:2]
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

    def _build_opening(
        self,
        *,
        full_name: str | None,
        vacancy_title: str,
        company: str | None,
        headline: str | None,
    ) -> str:
        vacancy_title = clean_vacancy_title(vacancy_title)
        company_phrase = f" в {company}" if company else ""
        name_sentence = f"Меня зовут {full_name}. " if full_name else ""

        headline_phrase = ""
        if headline:
            headline_phrase = f" Сейчас мой основной профессиональный фокус — {headline}."

        return (
            "Здравствуйте!\n\n"
            f"{name_sentence}Откликаюсь на позицию {vacancy_title}{company_phrase}, "
            "потому что мне интересны задачи роли и возможность приносить "
            "практическую пользу команде."
            f"{headline_phrase}"
        )

    def _build_relevance_paragraph(
        self,
        *,
        matched_keywords: list[str],
        selected_achievements: list[dict],
        selected_evidence: list[dict[str, Any]] | None = None,
        missing_keywords: list[str],
        profile_skills: list[str],
        vacancy_title: str,
        candidate_experiences: list[Any] | None = None,
        vacancy_fit_narrative: dict[str, Any] | None = None,
    ) -> str:
        vacancy_title = clean_vacancy_title(vacancy_title)
        parts: list[str] = []
        selected_evidence = selected_evidence or []
        vacancy_fit_narrative = vacancy_fit_narrative or {"critical_gaps": []}

        requirement_focus = self.narrative_builder.cover_letter_requirement_focus(
            matched_keywords=matched_keywords,
            vacancy_title=vacancy_title,
        )
        project_value = self.narrative_builder.cover_letter_project_value(
            selected_achievements=selected_achievements,
            selected_evidence=selected_evidence,
        )
        experience_value = self.narrative_builder.cover_letter_experience_value(
            vacancy_title=vacancy_title,
            matched_keywords=matched_keywords,
            candidate_experiences=candidate_experiences,
            is_supply_management_context=self._is_supply_management_context,
            compress_experience_phrases=self.narrative_builder.compress_experience_phrases,
        )
        supply_management_context = self._is_supply_management_context(
            vacancy_title=vacancy_title,
            matched_keywords=matched_keywords,
            phrases=[experience_value] if experience_value else [],
        )
        used_project_value = ""

        if supply_management_context and experience_value:
            parts.append(
                self._build_cover_letter_experience_sentence(
                    vacancy_title=vacancy_title,
                    experience_value=experience_value,
                    candidate_experiences=candidate_experiences,
                    selected_achievements=selected_achievements,
                )
            )
            if project_value:
                used_project_value = project_value
                parts.append(
                    self.cover_letter_humanizer.project_result_sentence(project_value)
                )
        elif requirement_focus and (experience_value or project_value):
            lead_project = self.narrative_builder.project_value_should_lead(project_value)
            if lead_project:
                if project_value:
                    used_project_value = project_value
                    parts.append(
                        self.cover_letter_humanizer.project_result_sentence(project_value)
                    )
                if experience_value:
                    parts.append(
                        self._build_cover_letter_experience_sentence(
                            vacancy_title=vacancy_title,
                            experience_value=experience_value,
                            candidate_experiences=candidate_experiences,
                            selected_achievements=selected_achievements,
                        )
                    )
                parts.append(
                    f"Особенно близки задачи, связанные с {requirement_focus}."
                )
            else:
                parts.append(
                    f"Особенно близки задачи, связанные с {requirement_focus}."
                )
                if experience_value:
                    parts.append(
                        self._build_cover_letter_experience_sentence(
                            vacancy_title=vacancy_title,
                            experience_value=experience_value,
                            candidate_experiences=candidate_experiences,
                            selected_achievements=selected_achievements,
                        )
                    )
                if project_value:
                    used_project_value = project_value
                    parts.append(
                        self.cover_letter_humanizer.project_result_sentence(project_value)
                    )
        elif requirement_focus:
            parts.append(
                f"Особенно близки задачи, связанные с {requirement_focus}. "
                "Буду рада обсудить, какие направления команды лучше всего связаны с моим опытом."
            )
        elif experience_value:
            parts.append(
                self._build_cover_letter_experience_sentence(
                    vacancy_title=vacancy_title,
                    experience_value=experience_value,
                    candidate_experiences=candidate_experiences,
                    selected_achievements=selected_achievements,
                )
            )
        elif project_value:
            used_project_value = project_value
            parts.append(
                self.cover_letter_humanizer.project_result_sentence(project_value)
            )

        result_value = self._cover_letter_result_value(
            selected_achievements=self._filter_result_achievements_not_in_project_block(
                selected_achievements=selected_achievements,
                project_value=used_project_value,
            )
        )
        if result_value:
            parts.append(
                f"Среди результатов, которыми особенно горжусь, — {result_value}."
            )

        gap_paragraph = self._build_gap_mitigation_paragraph(
            vacancy_fit_narrative=vacancy_fit_narrative,
            profile_skills=profile_skills,
            vacancy_title=vacancy_title,
        )
        if gap_paragraph:
            parts.append(gap_paragraph)

        # Fallback, если ничего не добавилось
        if not parts:
            parts.append(
                "Эта роль мне интересна, и я буду рада обсудить, "
                "какие задачи команды лучше всего связаны с моим текущим опытом."
            )

        return " ".join(parts)

    def _build_cover_letter_experience_sentence(
        self,
        *,
        vacancy_title: str,
        experience_value: str,
        candidate_experiences: list[Any] | None,
        selected_achievements: list[dict],
    ) -> str:
        return self.cover_letter_humanizer.experience_sentence(
            vacancy_title=vacancy_title,
            experience_value=experience_value,
            candidate_experiences=candidate_experiences,
            selected_achievements=selected_achievements,
            is_supply_management_context=self._is_supply_management_context(
                vacancy_title=vacancy_title,
                matched_keywords=[],
                phrases=[experience_value],
            ),
        )

    def _cover_letter_result_value(
        self,
        *,
        selected_achievements: list[dict],
    ) -> str:
        return self.achievement_verbalizer.cover_letter_result_value(
            selected_achievements=selected_achievements,
        )

    def _filter_result_achievements_not_in_project_block(
        self,
        *,
        selected_achievements: list[dict],
        project_value: str,
    ) -> list[dict]:
        if not project_value:
            return selected_achievements

        project_key = self._composition_overlap_key(project_value)
        result: list[dict] = []
        for item in selected_achievements:
            title = str(item.get("title") or "").strip()
            narrative_title = self.achievement_verbalizer.nounize_achievement_phrase(title)
            title_key = self._composition_overlap_key(narrative_title or title)
            if title_key and title_key in project_key:
                continue
            result.append(item)
        return result

    def _composition_overlap_key(self, value: str) -> str:
        return re.sub(r"[^0-9a-zа-яё]+", "", str(value or "").casefold())

    def _cover_letter_focus_from_headline(self, headline: str | None) -> str:
        if not headline:
            return "профессионального опыта, ответственности и задач роли"

        normalized = headline.lower()
        if "python" in normalized and any(
            marker in normalized for marker in ("automation", "ai", "llm", "workflow")
        ):
            return "Python-разработки, AI automation и workflow-систем"
        if "prompt" in normalized or "llm" in normalized:
            return "prompt engineering, AI tooling и автоматизации процессов"
        if "data" in normalized or "analytics" in normalized:
            return "аналитики данных, автоматизации и прикладной разработки"
        return "профессионального опыта, ответственности и задач роли"

    def _is_supply_management_context(
        self,
        *,
        vacancy_title: str,
        matched_keywords: list[str],
        phrases: list[str],
    ) -> bool:
        corpus = " ".join([vacancy_title, *matched_keywords, *phrases]).casefold()
        has_supply_domain = bool(
            re.search(r"(?<!водо)снабжен|закуп|мтс|поставщик|склад|логист", corpus)
        )
        has_management_signal = bool(
            re.search(r"начальник|руковод|управлен|бюджет|переговор|договор|претензи|контрол", corpus)
        )
        return has_supply_domain and has_management_signal

    def _select_cover_letter_evidence(
        self,
        *,
        vacancy_title: str,
        matched_keywords: list[str],
        missing_keywords: list[str],
        evidence_snippets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not evidence_snippets:
            return []

        return self.evidence_selection_service.rank_evidence(
            query_text=" ".join([vacancy_title, *matched_keywords, *missing_keywords]),
            evidence_items=evidence_snippets,
            required_skills=matched_keywords or missing_keywords,
            source_types=["achievement", "resume_structured", "resume", "github_public", "manual"],
            limit=4,
        )

    def _build_evidence_relevance_phrases(
        self,
        *,
        selected_evidence: list[dict[str, Any]],
        selected_achievements: list[dict],
    ) -> list[str]:
        achievement_titles = {
            re.sub(r"\s+", " ", str(item.get("title") or "").strip()).lower()
            for item in selected_achievements
            if str(item.get("title") or "").strip()
        }
        candidates: list[tuple[str, int, str]] = []
        for item in selected_evidence:
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            normalized_title = re.sub(r"\s+", " ", title).lower()
            if normalized_title in achievement_titles:
                continue
            display_title = self._display_evidence_title(title)
            skills = [
                cleaned
                for skill in (item.get("skills") or [])
                if (cleaned := self._normalize_display_skill(str(skill)))
                and cleaned.lower() not in LOW_SIGNAL_SKILLS
            ]
            skills = self._dedupe_preserve_order(skills)
            if display_title is None and not skills:
                continue
            if display_title is None:
                phrase = humanize_experience_phrase(", ".join(skills[:4]))
                candidates.append(
                    (
                        phrase,
                        score_alignment_item(
                            {
                                "requirement": phrase,
                                "evidence": phrase,
                                "confidence": item.get("confidence") or "medium",
                            }
                        ),
                        phrase,
                    )
                )
                continue
            if skills:
                phrase = f"{display_title} ({', '.join(skills[:3])})"
            else:
                phrase = display_title

            phrase = humanize_experience_phrase(phrase)
            candidates.append(
                (
                    display_title,
                    score_alignment_item(
                        {
                            "requirement": title,
                            "evidence": phrase,
                            "confidence": "high"
                            if str(item.get("source_type") or "").strip()
                            in {"achievement", "resume_structured"}
                            else "medium",
                        }
                    ),
                    phrase,
                )
            )

        if not candidates:
            return []

        kept_bases = dedupe_subsumed_phrases(
            self._dedupe_preserve_order([base for base, _, _ in candidates])
        )
        kept_base_keys = {str(base).casefold() for base in kept_bases}

        scored_phrases = [
            (score, phrase)
            for base, score, phrase in candidates
            if str(base).casefold() in kept_base_keys
        ]

        phrases = [
            phrase
            for _, phrase in sorted(scored_phrases, key=lambda pair: pair[0], reverse=True)
        ]
        return self._dedupe_preserve_order(phrases)

    def _display_evidence_title(self, title: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", title).strip(" .;-–—•")
        if not cleaned:
            return None

        lower = cleaned.lower()
        if lower in PROJECT_DISPLAY_HINTS:
            return make_user_facing_evidence_phrase(cleaned)
        if lower in {"technology stack from resume", "technologies from resume"}:
            return None
        return make_user_facing_evidence_phrase(cleaned)

    def _normalize_display_skill(self, value: str) -> str:
        cleaned = re.sub(
            r"^(Technologies|AI tools|Automation tools)\s*:\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .;-–—•")

        replacements = {
            "llm": "LLM",
            "chatgpt": "ChatGPT",
            "openai": "OpenAI",
            "ai workflow": "AI Workflow",
            "no-code": "No-code",
        }

        lower = cleaned.lower()
        return replacements.get(lower, cleaned)

    def _build_evidence_relevance(
        self,
        *,
        selected_evidence: list[dict[str, Any]],
        selected_achievements: list[dict],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()

        for achievement in selected_achievements:
            title = str(achievement.get("title") or "").strip()
            display_title = make_user_facing_evidence_phrase(title)
            if not display_title:
                continue
            key = display_title.lower()
            seen.add(key)
            items.append(
                {
                    "evidence_id": achievement.get("id"),
                    "title": display_title,
                    "source_type": "achievement",
                    "fact_status": achievement.get("fact_status") or "confirmed",
                    "evidence_strength": "medium",
                    "skills": [],
                    "reason": achievement.get("reason") or "selected achievement",
                }
            )

        for evidence in selected_evidence:
            title = str(evidence.get("title") or "").strip()
            display_title = make_user_facing_evidence_phrase(title)
            display_skills = [
                cleaned
                for skill in (evidence.get("skills") or [])
                if (cleaned := self._normalize_display_skill(str(skill)))
                and cleaned.lower() not in LOW_SIGNAL_SKILLS
            ]
            display_skills = self._dedupe_preserve_order(display_skills)
            if display_title is None and display_skills:
                display_title = ", ".join(display_skills[:3])
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            key = evidence_id or str(display_title or "").lower()
            if not display_title or key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "evidence_id": evidence_id or None,
                    "title": display_title,
                    "source_type": evidence.get("source_type"),
                    "fact_status": evidence.get("fact_status"),
                    "evidence_strength": evidence.get("evidence_strength"),
                    "skills": display_skills,
                    "reason": evidence.get("reason"),
                }
            )

        return items[:6]

    def _find_evidence_for_keyword(
        self,
        keyword: str,
        evidence_items: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        normalized_keyword = keyword.strip().lower().replace(" ", "_")
        for item in evidence_items:
            skills = {
                str(skill).strip().lower().replace(" ", "_")
                for skill in (item.get("skills") or [])
                if str(skill).strip()
            }
            title = str(item.get("title") or "").lower()
            if normalized_keyword in skills or keyword.strip().lower() in title:
                return item
        return evidence_items[0] if evidence_items else None

    def _build_closing(
        self,
        *,
        vacancy_title: str,
        company: str | None,
        candidate_experiences: list[Any] | None = None,
        selected_skills: list[str] | None = None,
        matched_keywords: list[str] | None = None,
        selected_achievements: list[dict] | None = None,
    ) -> str:
        vacancy_title = clean_vacancy_title(vacancy_title)
        gender = self.cover_letter_humanizer.candidate_gender(
            full_name=None,
            text=" ".join(
                [
                    *[str(skill) for skill in selected_skills or []],
                    *[
                        str(item.get("title") or "")
                        for item in selected_achievements or []
                        if isinstance(item, dict)
                    ],
                ]
            ),
        )
        ready = self.cover_letter_humanizer.ready_word(gender=gender)
        glad = self.cover_letter_humanizer.glad_word(gender=gender)
        if self._is_supply_management_context(
            vacancy_title=vacancy_title,
            matched_keywords=matched_keywords or [],
            phrases=[
                *[str(getattr(exp, "description_raw", "") or "") for exp in candidate_experiences or []],
                *(selected_skills or []),
            ],
        ):
            return (
                f"{ready.capitalize()} применять накопленный опыт в организации закупок, контроле поставок, "
                "работе с поставщиками и снижении затрат на снабжение. "
                f"Буду {glad} обсудить, чем мой опыт может быть полезен вашей команде."
            )
        focus = self._closing_focus_from_requirements(
            vacancy_title=vacancy_title,
            matched_keywords=matched_keywords or [],
            selected_skills=selected_skills or [],
        )
        if focus:
            return (
                f"{ready.capitalize()} применять накопленный опыт в задачах, связанных с {focus}. "
                f"Буду {glad} обсудить, чем мой опыт может быть полезен вашей команде."
            )
        return (
            f"{ready.capitalize()} применять свой опыт для аккуратного выполнения задач, "
            "ответственности за результат и быстрого включения в процессы. "
            f"Буду {glad} обсудить, чем мой опыт может быть полезен вашей команде."
        )

    def _closing_focus_from_requirements(
        self,
        *,
        vacancy_title: str,
        matched_keywords: list[str],
        selected_skills: list[str],
    ) -> str:
        vacancy_key = self._closing_noise_key(vacancy_title)
        candidates = [
            self._normalize_display_skill(str(value or ""))
            for value in [*matched_keywords, *selected_skills]
        ]
        useful = [
            value
            for value in candidates
            if value
            and value.lower() not in LOW_SIGNAL_SKILLS
            and not self._looks_like_closing_noise(value, vacancy_key=vacancy_key)
        ]
        phrases = [
            self._closing_focus_phrase(value)
            for value in self._dedupe_preserve_order(useful)[:2]
        ]
        return self.cover_letter_humanizer.join_experience_phrases(phrases)

    def _closing_focus_phrase(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        lowered = normalized.casefold()

        replacements = {
            "гражданское право": "гражданским правом",
            "договорное право": "договорным правом",
            "договорная работа": "договорной работой",
            "претензионная работа": "претензионной работой",
            "документооборот": "документооборотом",
            "арбитраж": "арбитражной практикой",
            "legal research": "правовым анализом",
        }
        if lowered in replacements:
            return replacements[lowered]

        return humanize_experience_phrase(normalized)

    def _looks_like_closing_noise(self, value: str, *, vacancy_key: str) -> bool:
        normalized = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        if not normalized:
            return True
        lowered = normalized.casefold()
        key = self._closing_noise_key(normalized)
        if key and vacancy_key and (key == vacancy_key or key in vacancy_key or vacancy_key in key):
            return True
        if re.match(
            r"^(подготовил|подготовила|сократил|сократила|ускорил|ускорила|навел|навела|"
            r"внедрил|внедрила|разработал|разработала|создал|создала|участвовал|участвовала)\b",
            lowered,
        ):
            return True
        if re.fullmatch(
            r"(юрист|врач(?:[-\s].*)?|сантехник|слесарь[-\s]сантехник|бухгалтер|"
            r"legal research|документооборот|сантехника)",
            lowered,
        ):
            return True
        return not re.search(
            r"работ|подготов|сопровожд|консульт|ведени|документац|диагност|"
            r"монтаж|обслужив|ремонт|договор|претензи|сверк",
            lowered,
        )

    def _closing_noise_key(self, value: str) -> str:
        return re.sub(r"[^0-9a-zа-яё]+", "", str(value or "").casefold())

    def _is_business_management_context(
        self,
        *,
        vacancy_title: str,
        candidate_experiences: list[Any] | None,
        selected_skills: list[str] | None,
    ) -> bool:
        corpus_parts = [vacancy_title]
        for exp in candidate_experiences or []:
            corpus_parts.append(str(getattr(exp, "description_raw", "") or ""))
        corpus_parts.extend(selected_skills or [])
        corpus = " ".join(corpus_parts).casefold()
        return any(re.search(marker, corpus) for marker in BUSINESS_MANAGEMENT_MARKERS)

    def _build_gap_mitigation_paragraph(
        self,
        *,
        vacancy_fit_narrative: dict[str, Any],
        profile_skills: list[str],
        vacancy_title: str,
    ) -> str | None:
        return self.narrative_builder.build_gap_mitigation_paragraph(
            vacancy_fit_narrative=vacancy_fit_narrative,
            profile_skills=profile_skills,
            vacancy_title=vacancy_title,
        )

    def _build_gap_mitigations(
        self,
        *,
        critical_gaps: list[str],
        vacancy_title: str,
    ) -> list[GapMitigation]:
        vacancy_title = clean_vacancy_title(vacancy_title)
        bridge_phrases = {
            "FastAPI": "имею опыт работы с async-фреймворками (Starlette, aiohttp) и готов быстро адаптироваться под FastAPI",
            "PostgreSQL": "работаю с реляционными СУБД и знаком с принципами оптимизации запросов",
            "Docker": "использую контейнеризацию в локальной разработке и готов углубить практику в CI/CD",
            "Redis": "понимаю принципы кэширования и работы с in-memory хранилищами",
            "CI/CD": "настраивал базовые пайплайны деплоя и готов активно развивать эту компетенцию",
            "Kubernetes": "изучаю оркестрацию контейнеров и готов применять знания на практике",
            "AWS": "имею опыт работы с облачными сервисами и готов освоить специфичные для роли инструменты",
            "Automation": "развиваю навыки автоматизации тестирования и рабочих процессов",
            "Automation Tooling": "развиваю навыки автоматизации тестирования и рабочих процессов",
        }

        mitigations: list[GapMitigation] = []
        for gap in critical_gaps:
            phrase = bridge_phrases.get(gap)
            if phrase:
                mitigations.append(
                    GapMitigation(
                        keyword=gap,
                        mitigation_text=phrase,
                    )
                )
            else:
                if gap.lower() in {"automation", "automation tooling"}:
                    mitigations.append(
                        GapMitigation(
                            keyword=gap,
                            mitigation_text=(
                                "развиваю навыки автоматизации тестирования и готов "
                                "усилить практику в рамках онбординга"
                            ),
                        )
                    )
                    continue
                mitigations.append(
                    GapMitigation(
                        keyword=gap,
                        mitigation_text=(
                            f"готов усилить практику по {gap} в рамках онбординга на позиции {vacancy_title}"
                        ),
                    )
                )

        return mitigations

    def _render_gap_focus(self, critical_gaps: list[str]) -> str | None:
        if not critical_gaps:
            return None

        rendered_gaps: list[str] = []
        for gap in critical_gaps[:2]:
            rendered_gaps.append(self.narrative_builder.to_gap_case(gap))

        rendered_gaps = [gap for gap in rendered_gaps if gap]
        if not rendered_gaps:
            return None
        if len(rendered_gaps) == 1:
            return rendered_gaps[0]
        return f"{rendered_gaps[0]} и {rendered_gaps[1]}"

    def _build_claims_needing_confirmation(
        self,
        *,
        selected_achievements: list[dict],
    ) -> list[dict]:
        return [
            build_claim(
                claim_type="achievement",
                text=ensure_selected_achievement(item).title,
                fact_status=ensure_selected_achievement(item).fact_status,
                source="candidate_achievements",
            )
            for item in selected_achievements
            if ensure_selected_achievement(item).fact_status != "confirmed"
        ]

    def _build_selection_rationale(
        self,
        *,
        matched_keywords: list[str],
        selected_achievements: list[dict],
    ) -> list[dict]:
        rationale: list[dict] = []

        for keyword in matched_keywords[:6]:
            rationale.append(
                {
                    "item": keyword,
                    "type": "keyword",
                    "reason": "vacancy_overlap",
                }
            )

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
        matched_keywords: list[str],
        missing_keywords: list[str],
        selected_achievements: list[dict],
        selected_evidence_reason: list[dict[str, Any]] | None = None,
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

        if selected_evidence_reason and self._has_unconfirmed_selected_evidence(selected_evidence_reason):
            warnings.append(
                build_warning(
                    code="unconfirmed_selected_evidence",
                    message=(
                        "selected evidence includes snippets that still require human confirmation"
                    ),
                    severity="warning",
                )
            )

        if missing_keywords:
            warnings.append(
                build_warning(
                    code="missing_vacancy_keywords",
                    message=(
                        "profile does not strongly support these vacancy keywords yet: "
                        f"{', '.join(missing_keywords[:6])}"
                    ),
                    severity="warning",
                )
            )

        if not matched_keywords:
            warnings.append(
                build_warning(
                    code="weak_profile_overlap",
                    message=(
                        "current letter has weak profile-to-vacancy overlap and "
                        "needs stronger factual grounding"
                    ),
                    severity="warning",
                )
            )

        warnings.append(
            build_warning(
                code="draft_review_required",
                message="cover letter draft should be reviewed before sending",
                severity="info",
            )
        )
        return warnings

    def _filter_document_usable_evidence(
        self,
        evidence_snippets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            item
            for item in evidence_snippets
            if str(item.get("fact_status") or "").strip().lower() != "rejected"
        ]

    def _has_unconfirmed_selected_evidence(
        self,
        selected_evidence_reason: list[dict[str, Any]],
    ) -> bool:
        return any(
            str(item.get("fact_status") or "").strip().lower()
            in {"needs_confirmation", "unverified", "partial"}
            for item in selected_evidence_reason
        )

    def _build_confidence_assessment(
        self,
        *,
        selected_achievements: list[dict],
        selected_evidence_reason: list[dict[str, Any]] | None = None,
        missing_keywords: list[str],
    ):
        evidence_items = selected_evidence_reason or selected_achievements
        assessment = aggregate_evidence_confidence(
            [
                self._confidence_item_from_achievement(item)
                if "evidence_id" not in item
                else item
                for item in evidence_items
            ]
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

    def _extract_contact_info(self, raw_text: str) -> dict[str, str | None]:
        if not raw_text:
            return {}

        return {
            "email": self._extract_email(raw_text),
            "phone": self._extract_phone(raw_text),
            "github": self._extract_github(raw_text),
            "telegram": self._extract_telegram(raw_text),
        }

    def _extract_email(self, text: str) -> str | None:
        match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        return match.group(0).strip() if match else None

    def _extract_phone(self, text: str) -> str | None:
        match = re.search(r"(?:\+?\d[\d\s().-]{8,}\d)", text)
        if not match:
            return None
        return re.sub(r"\s+", " ", match.group(0)).strip()

    def _extract_github(self, text: str) -> str | None:
        match = re.search(
            r"(?:https?://)?github\.com/[A-Za-z0-9_.-]+/?",
            text,
            re.IGNORECASE,
        )
        return match.group(0).rstrip("/") if match else None

    def _extract_telegram(self, text: str) -> str | None:
        match = re.search(
            r"(?<![\w.+-])(?:https?://t\.me/[A-Za-z0-9_]+|t\.me/[A-Za-z0-9_]+|@[A-Za-z0-9_]{5,})",
            text,
            re.IGNORECASE,
        )
        return match.group(0).strip() if match else None

    def _build_draft(
        self,
        *,
        vacancy_title: str,
        company: str,
        strengths: list[str],
        gaps: list[str],
        achievements: list[str],
    ) -> str:
        vacancy_title = clean_vacancy_title(vacancy_title)
        parts = []

        parts.append(
            f"Откликаюсь на позицию {vacancy_title} в {company}, потому что мне интересны задачи роли "
            "и возможность приносить практическую пользу команде."
        )

        if strengths:
            parts.append(
                "Особенно близки задачи, связанные с "
                + ", ".join(strengths[:3])
                + "."
            )

        if achievements:
            parts.append(
                self.achievement_verbalizer.achievement_result_sentence(achievements)
            )

        if gaps:
            parts.append(
                "Отдельно готов обсудить план быстрого погружения: "
                + ", ".join(gaps[:2])
                + "."
            )

        parts.append(
            "Готов применять свой опыт для аккуратного выполнения задач, ответственности за результат "
            "и быстрого включения в процессы."
        )

        return "\n\n".join(parts)

    def _word_count(self, text: str) -> int:
        return len(text.split())

    def _is_safe_enhancement(self, original: str, enhanced: str) -> bool:
        orig_words = self._word_count(original)
        enh_words = self._word_count(enhanced)

        # 1. защита от пустого / деградации
        if enh_words == 0:
            return False

        # 2. слишком сильное сжатие
        if enh_words < orig_words * 0.5:
            return False

        # 3. слишком сильное раздувание (более мягкое)
        if enh_words > orig_words * 2.5:
            return False

        # 4. ключевые слова не должны исчезнуть
        for word in original.split():
            # Убираем пунктуацию для сравнения
            clean_word = re.sub(r'[^\w]', '', word).lower()
            if len(clean_word) > 4 and clean_word not in enhanced.lower():
                return False

        return True

    async def enhance_cover_letter_with_ai(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        draft_text: str,
        language: str = "ru",
    ) -> str:
        if not self.ai_orchestrator:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI orchestrator not configured",
            )

        from app.ai.use_cases.cover_letter_enhance import enhance_cover_letter

        result = await enhance_cover_letter(
            self.ai_orchestrator,
            session,
            user_id=user_id,
            draft_text=draft_text,
            language=language,
        )

        enhanced = result["result"]["enhanced_text"]

        if not self._is_safe_enhancement(draft_text, enhanced):
            return draft_text

        return enhanced
