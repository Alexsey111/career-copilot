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
from app.services.profile_structuring_service import ProfileStructuringService
from app.services.legacy_resume_recovery_service import LegacyResumeRecoveryService
from app.services.resume_renderer import render_resume
from app.services.core_service_policy import LEGACY_CANDIDATE_SPECIFIC_HEURISTIC


LEGACY_DOMAIN_SPECIFIC_SYNTHESIS = LEGACY_CANDIDATE_SPECIFIC_HEURISTIC


MAX_RESUME_WORDS = 1200
MAX_KEYWORD_LOSS_RATIO = 0.3
MAX_RESUME_ACHIEVEMENTS = None

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

LOW_SIGNAL_SKILLS = {
    "html",
    "mako",
    "dockerfile",
    "powershell",
}

KNOWN_MULTIWORD_SKILLS = [
    "Гражданское право",
    "Договорное право",
    "Legal Research",
    "Документооборот",
    "Арбитраж",
    "1С:Бухгалтерия",
    "Первичная документация",
    "Сверка взаиморасчётов",
    "Банк-клиент",
    "Excel",
    "НДС",
    "Акты сверки",
    "Деловая переписка",
    "Складская логистика",
    "Управление персоналом",
    "Контроль качества",
]

EXPERIENCE_RESPONSIBILITY_BOUNDARIES = [
    "Организация складских процессов",
    "Ведение медицинской документации",
    "Координация маршрутизации пациентов",
    "Претензионная работа",
]

DISPLAY_NORMALIZATION_MAP = {
    "devloher": "developer",
    "chatgpt": "ChatGPT",
    "llm": "LLM",
    "ai": "AI",
    "openai": "OpenAI",
    "ai workflow": "AI Workflow",
    "no-code": "No-code",
}

ACHIEVEMENT_CATEGORIES = {
    "github_architecture",
    "automation_project",
    "computer_vision",
    "analytics_project",
    "backend_project",
    "ai_workflow",
}

PROJECT_EVIDENCE_CATEGORIES = {
    "project",
    "ai_project",
    "automation",
    "prompt_engineering",
    "internship",
    "portfolio_project",
    "achievement",
    "architecture_evidence",
    *ACHIEVEMENT_CATEGORIES,
}

ENGINEERING_ACHIEVEMENT_CATEGORIES = {
    "github_architecture",
    "backend_project",
    "architecture_evidence",
}
AUTOMATION_ACHIEVEMENT_CATEGORIES = {
    "automation_project",
    "automation",
    "prompt_engineering",
    "ai_project",
    "ai_workflow",
}
BUSINESS_DOMAIN_ACHIEVEMENT_CATEGORIES = {
    "computer_vision",
    "analytics_project",
    "project",
    "internship",
    "achievement",
}

EVIDENCE_DIVERSITY_BUCKET_LIMITS = {
    "backend": 2,
    "automation": 2,
    "computer_vision": 1,
    "analytics": 1,
    "ai_workflow": 2,
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
        enable_legacy_recovery: bool = True,
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
        self.legacy_recovery_service = LegacyResumeRecoveryService(
            enabled=enable_legacy_recovery,
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

        latest_extraction = await self.file_extraction_repository.get_latest_for_active_source_file_kind(
            session,
            user_id,
            file_kind="resume",
        )
        contact_info = self._extract_contact_info(
            latest_extraction.extracted_text if latest_extraction else ""
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
        evidence_snippets = self._filter_document_usable_evidence(evidence_snippets)

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
                    "fact_status": str(
                        snippet.get("fact_status") or item.get("fact_status") or ""
                    ).strip() or "confirmed",
                    "evidence_strength": str(snippet.get("evidence_strength") or "").strip() or None,
                    "source_type": str(snippet.get("source_type") or "").strip() or None,
                    "category": self._achievement_category_from_evidence(snippet),
                    "provenance_label": self._provenance_label_from_evidence(snippet),
                    "skills": list(snippet.get("skills") or []),
                }
            )

        if not selected_evidence_ids and evidence_snippets:
            ranked_evidence = self.evidence_selection_service.rank_evidence(
                query_text=" ".join(matched_keywords or missing_keywords),
                evidence_items=evidence_snippets,
                required_skills=matched_keywords or missing_keywords,
                source_types=EVIDENCE_BANK_SOURCE_TYPES,
                limit=12,
            )
            fallback_ranked_evidence = self._balance_ranked_evidence_selection(
                ranked_evidence=ranked_evidence,
                evidence_by_id=evidence_by_id,
                limit=5,
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
                        "source_type": str(item.get("source_type") or snippet.get("source_type") or "").strip()
                        or None,
                        "category": self._achievement_category_from_evidence(snippet or item),
                        "provenance_label": self._provenance_label_from_evidence(snippet or item),
                        "skills": list(item.get("skills") or snippet.get("skills") or []),
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
        experience_items = self._build_experience_items(profile)

        tailoring = self._build_ats_tailoring_sections(
            vacancy_title=vacancy.title,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            evidence_snippets=evidence_snippets,
            experience_items=experience_items,
        )

        summary_bullets = self._build_summary_bullets(
            profile=profile,
            vacancy_title=vacancy.title,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            matched_keywords=matched_keywords,
        )

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
            selected_evidence_reason=selected_evidence_reason,
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

        selected_achievements = self._add_project_narratives(selected_achievements)

        project_sections: list[dict[str, Any]] = []
        if not experience_items:
            project_sections = self._build_project_sections(
                selected_achievements
            )
        education_items = self._build_education_items(
            profile,
            latest_extraction.extracted_text if latest_extraction else "",
        )
        course_items = self._build_course_items(
            latest_extraction.extracted_text if latest_extraction else "",
        )
        internship_items = self._build_internship_items(
            latest_extraction.extracted_text if latest_extraction else "",
        )

        content_json = build_resume_content(
            candidate={
                "full_name": profile.full_name,
                "headline": profile.headline,
                "location": profile.location,
                "contacts": contact_info,
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
            project_sections=project_sections,
            summary_bullets=summary_bullets,
            skills=selected_skills,
            experience=experience_items,
            education=education_items,
            courses=course_items,
            internships=internship_items,
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

    def _extract_skills_from_profile_or_raw_text(
        self,
        *,
        profile_summary: str | None,
        raw_text: str,
    ) -> list[str]:
        raw_text_skills = self._extract_skills_from_raw_text(raw_text)
        if raw_text_skills:
            return raw_text_skills

        return self._split_skill_text(profile_summary or "")

    def _split_skill_text(self, text: str) -> list[str]:
        if not text:
            return []

        remaining = re.sub(
            r"\s+(?:образование|опыт работы|опыт|курсы|проекты|стажировки|контакты|достижения|о себе)\s*[:：].*$",
            "",
            str(text),
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        remaining = re.sub(
            r"(?m)^[•\s\d]+$",
            "",
            remaining,
        ).strip()

        extracted: list[str] = []

        for skill in KNOWN_MULTIWORD_SKILLS:
            if re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", remaining, re.IGNORECASE):
                extracted.append(skill)
                remaining = re.sub(
                    rf"(?<!\w){re.escape(skill)}(?!\w)",
                    "\n",
                    remaining,
                    flags=re.IGNORECASE,
                )

        parts = re.split(r"[,\n;]+", remaining)
        cleaned_parts = [
            cleaned
            for part in parts
            if (cleaned := self._clean_skill_candidate(part))
        ]
        return self._dedupe_preserve_order([*extracted, *cleaned_parts])

    def _clean_skill_candidate(self, value: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", value.strip(" .;-–—•"))
        if not cleaned:
            return None

        if re.fullmatch(r"[•\s\d]+", cleaned):
            return None

        if re.fullmatch(r"\d+", cleaned):
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
        stop_headings = {
            "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
            "ОПЫТ РАБОТЫ",
            "ОБРАЗОВАНИЕ",
            "ПРОЕКТЫ",
            "СТАЖИРОВКИ",
            "КОНТАКТЫ",
            "О СЕБЕ",
            "КУРСЫ",
            "ДОСТИЖЕНИЯ",
        }

        for line in lines:
            heading_match = re.match(
                r"^(ПРОФЕССИОНАЛЬНЫЕ\s+НАВЫКИ|НАВЫКИ)\s*[:：-]?\s*(.*)$",
                line,
                flags=re.IGNORECASE,
            )
            if heading_match:
                capture = True
                remainder = heading_match.group(2).strip()
                if remainder:
                    section_lines.append(remainder)
                continue

            normalized = re.sub(r"[:：-]+$", "", line).strip().upper()

            if capture and normalized in stop_headings:
                break

            if capture:
                section_lines.append(line)

        if not section_lines:
            return []

        joined = "\n".join(section_lines)
        return self._split_skill_text(joined)

    def _select_resume_skills(
        self,
        *,
        raw_skills: list[str],
        matched_keywords: list[str],
    ) -> list[str]:
        matched_skills: list[str] = []
        raw_skill_set = {
            self._normalize_display_skill(skill).strip().lower()
            for skill in raw_skills
            if skill
        }

        for keyword in matched_keywords:
            normalized_keyword = self._normalize_display_skill(keyword).strip().lower()
            if normalized_keyword not in raw_skill_set:
                continue

            for raw_skill in raw_skills:
                if self._skill_matches_keyword(raw_skill, keyword):
                    matched_skills.append(raw_skill)

        matched_skills = self._dedupe_preserve_order(matched_skills)
        remaining = [skill for skill in raw_skills if skill not in matched_skills]
        combined = matched_skills + remaining

        normalized: list[str] = []
        for item in combined:
            cleaned = self._normalize_display_skill(item)
            if cleaned.lower() in LOW_SIGNAL_SKILLS:
                continue
            normalized.append(cleaned)

        return self._dedupe_preserve_order(normalized)[:10]

    def _normalize_display_skill(self, value: str) -> str:
        cleaned = re.sub(
            r"^(Technologies|AI tools|Automation tools)\s*:\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .;-–—•")

        lower = cleaned.lower()
        return DISPLAY_NORMALIZATION_MAP.get(lower, cleaned)

    def _skill_matches_keyword(self, raw_skill: str, keyword: str) -> bool:
        raw = self._normalize_display_skill(raw_skill).strip().lower()
        key = self._normalize_display_skill(keyword).strip().lower()

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
        limit = MAX_RESUME_ACHIEVEMENTS
        if limit:
            selected = selected[:limit]

        return [
            achievement_to_dict(item)
            for item in selected
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
            if category not in PROJECT_EVIDENCE_CATEGORIES:
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
                    "skills": list(snippet.get("skills") or []),
                }
            )
            if len(selected) >= 5:
                break
        return selected

    def _add_project_narratives(
        self,
        selected_achievements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        # Legacy marker: existing domain-specific synthesis must not be extended.
        enriched: list[dict[str, Any]] = []

        for item in selected_achievements:
            enriched_item = dict(item)
            title = str(item.get("title") or "").lower()
            action = str(item.get("action") or "")
            skills = [
                str(skill).strip()
                for skill in (item.get("skills") or [])
                if str(skill).strip()
            ]

            corpus = " ".join([title, action, " ".join(skills)]).lower()

            if "workflow orchestration" in corpus or "ai workflow" in corpus:
                enriched_item["narrative"] = (
                    "workflow/orchestration implementation signals; ownership requires review"
                )
            elif "fastapi" in corpus or "backend" in corpus:
                enriched_item["narrative"] = (
                    "backend/API implementation signals; ownership requires review"
                )
            elif "computer vision" in corpus or "мониторинг" in corpus:
                enriched_item["narrative"] = (
                    "AI/CV pipeline для анализа изображений или видео и поддержки "
                    "прикладного мониторинга"
                )
            elif "analytics" in corpus or "анализ" in corpus:
                enriched_item["narrative"] = (
                    "аналитический pipeline для обработки данных и извлечения полезных сигналов"
                )

            enriched.append(enriched_item)

        return enriched

    def _build_project_sections(
        self,
        selected_achievements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}

        for item in selected_achievements:
            if not self._allows_strong_project_claim(item):
                continue
            project_name = self._project_name_from_achievement(item)
            role = self._project_role_from_achievement(item)
            bullets = self._project_bullets_from_achievement(item)
            if not bullets:
                continue

            section = grouped.setdefault(
                project_name,
                {
                    "project": project_name,
                    "role": role,
                    "bullets": [],
                },
            )
            if not section.get("role") and role:
                section["role"] = role
            section["bullets"] = self._dedupe_project_bullets(
                [*section["bullets"], *bullets]
            )[:5]

        return list(grouped.values())[:4]

    def _allows_strong_project_claim(self, achievement: dict[str, Any]) -> bool:
        fact_status = str(achievement.get("fact_status") or "").strip().lower()
        ownership_confidence = str(
            achievement.get("ownership_confidence")
            or achievement.get("candidate_ownership_confidence")
            or "medium"
        ).strip().lower()
        requires_confirmation = bool(achievement.get("requires_confirmation") is True)

        if requires_confirmation:
            return False
        if ownership_confidence in {"low", "unknown", "needs_review"}:
            return False
        return fact_status in {"confirmed", "user_provided"}

    def _build_education_items(
        self,
        profile,
        latest_extraction_text: str = "",
    ) -> list[dict[str, Any]]:
        if not latest_extraction_text:
            return []

        lines = [
            line.strip()
            for line in latest_extraction_text.splitlines()
            if line.strip()
        ]
        section = self._extract_raw_section(
            lines,
            start_heading="ОБРАЗОВАНИЕ",
            stop_headings={
                "ПРОЕКТЫ",
                "ПОРТФОЛИО",
                "СТАЖИРОВКИ",
                "КУРСЫ",
                "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ",
                "КОНТАКТЫ",
                "О СЕБЕ",
            },
        )

        if not section:
            return []

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for line in [*section, " ".join(section)]:
            for details in self._extract_formal_education_details(line):
                normalized = details.casefold()
                if normalized in seen:
                    continue
                seen.add(normalized)
                items.append({"details": details})

        return items[:4]

    def _build_course_items(
        self,
        latest_extraction_text: str = "",
    ) -> list[dict[str, Any]]:
        if not latest_extraction_text:
            return []

        lines = [
            line.strip()
            for line in latest_extraction_text.splitlines()
            if line.strip()
        ]

        sections: list[str] = []
        course_section = self._extract_raw_section(
            lines,
            start_heading="КУРСЫ",
            stop_headings={
                "ПРОЕКТЫ",
                "ПОРТФОЛИО",
                "СТАЖИРОВКИ",
                "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ",
                "КОНТАКТЫ",
                "О СЕБЕ",
            },
        )
        if course_section:
            sections.extend(course_section)

        education_section = self._extract_raw_section(
            lines,
            start_heading="ОБРАЗОВАНИЕ",
            stop_headings={
                "ПРОЕКТЫ",
                "ПОРТФОЛИО",
                "СТАЖИРОВКИ",
                "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ",
                "КОНТАКТЫ",
                "О СЕБЕ",
            },
        )
        if education_section:
            sections.extend(education_section)

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for line in [*sections, " ".join(sections)]:
            for item in self._extract_course_details(line):
                key = str(item.get("details") or "").casefold()
                if not key or key in seen:
                    continue
                seen.add(key)
                items.append(item)

        return items[:6]

    def _build_internship_items(
        self,
        latest_extraction_text: str = "",
    ) -> list[dict[str, Any]]:
        if not latest_extraction_text:
            return []

        draft = ProfileStructuringService()._build_draft(latest_extraction_text)
        items: list[dict[str, Any]] = []

        for internship in draft.internships:
            title = re.sub(r"\s+", " ", str(internship.title or "")).strip()
            snippet_text = re.sub(
                r"\s+",
                " ",
                str(internship.snippet_text or "").strip(),
            )
            if not title:
                continue

            details = title
            if snippet_text and snippet_text.casefold() != title.casefold():
                details = f"{title} — {snippet_text}"
                if len(details) > 220:
                    details = details[:220].rsplit(" ", 1)[0].strip()

            items.append(
                {
                    "title": title,
                    "details": details,
                    "snippet_text": snippet_text or title,
                    "skills": list(internship.skills or []),
                    "category": "internship",
                }
            )

        return self._dedupe_dicts_by_key(items, key="title")

    def _dedupe_dicts_by_key(
        self,
        items: list[dict[str, Any]],
        *,
        key: str,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            marker = str(item.get(key) or "").strip().casefold()
            if not marker or marker in seen:
                continue
            seen.add(marker)
            result.append(item)
        return result

    def _extract_formal_education_details(self, value: str) -> list[str]:
        return self.legacy_recovery_service.recover_known_formal_education_lines(value)

    def _extract_course_details(self, value: str) -> list[dict[str, Any]]:
        return [
            {
                "title": item,
                "provider": None,
                "year": None,
                "details": item,
            }
            for item in self.legacy_recovery_service.recover_known_course_lines(value)
        ]

    def _normalize_layout_text(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        return text.strip(" -–—•")

    def _looks_like_mixed_layout_noise(self, value: str) -> bool:
        return self.legacy_recovery_service.looks_like_legacy_mixed_education_layout_noise(value)

    def _looks_like_standalone_education_line(self, value: str) -> bool:
        text = self._normalize_layout_text(value)
        lowered = text.lower()
        if len(text) < 18 or len(text) > 180:
            return False
        if any(marker in text for marker in ("»", ")", "(", "/", "|")):
            return False
        if any(
            marker in lowered
            for marker in (
                "программист на python",
                "аналитик данных",
                "chatgpt",
                "искусственного интеллекта",
                "специальность",
                "высшее образование",
                "среднее образование",
                "бакалавр",
                "магистр",
            )
        ):
            return False
        return lowered.startswith(
            (
                "алтай",
                "рязан",
                "москов",
                "санкт-петербург",
                "университет",
                "институт",
                "колледж",
                "техникум",
                "академия",
            )
        )

    def _extract_raw_section(
        self,
        lines: list[str],
        *,
        start_heading: str,
        stop_headings: set[str],
    ) -> list[str]:
        capture = False
        result: list[str] = []

        for line in lines:
            normalized = re.sub(r"[:：]+$", "", line.strip()).upper()

            if normalized == start_heading or normalized.startswith(f"{start_heading} "):
                capture = True
                remainder = re.sub(
                    rf"^{re.escape(start_heading)}\s*",
                    "",
                    normalized,
                    flags=re.IGNORECASE,
                ).strip()
                if remainder:
                    result.append(line)
                continue

            if capture and normalized in stop_headings:
                break

            if capture:
                result.append(line)

        return result

    def _dedupe_project_bullets(self, bullets: list[str]) -> list[str]:
        selected: list[str] = []
        seen_text: set[str] = set()
        seen_concepts: set[str] = set()

        for bullet in bullets:
            cleaned = re.sub(r"\s+", " ", str(bullet).strip())
            normalized = cleaned.lower()
            if not normalized or normalized in seen_text:
                continue

            concept = self._project_bullet_concept(normalized)
            if concept and concept in seen_concepts:
                continue

            seen_text.add(normalized)
            if concept:
                seen_concepts.add(concept)
            selected.append(cleaned)

        return selected

    def _project_bullet_concept(self, normalized_bullet: str) -> str | None:
        if "fastapi" in normalized_bullet or "backend" in normalized_bullet:
            return "backend"
        if "workflow" in normalized_bullet and (
            "orchestration" in normalized_bullet
            or "генерации" in normalized_bullet
        ):
            return "workflow"
        if "persistence" in normalized_bullet or "postgresql" in normalized_bullet:
            return "persistence"
        if "computer vision" in normalized_bullet or "мониторинг" in normalized_bullet:
            return "computer_vision"
        if "analytics" in normalized_bullet or "аналит" in normalized_bullet:
            return "analytics"
        return None

    def _project_name_from_achievement(self, achievement: dict[str, Any]) -> str:
        title = str(achievement.get("title") or "").strip()
        if title:
            return title

        corpus = self._achievement_semantic_corpus(achievement)

        if any(marker in corpus for marker in ("computer vision", "cv", "изображен", "video", "видео")):
            return "Visual Data Processing Project"

        if any(marker in corpus for marker in ("analytics", "data pipeline", "аналит")):
            return "Analytics Project"

        if any(marker in corpus for marker in ("workflow orchestration", "ai workflow", "pipeline")):
            return "Workflow Implementation Project"

        if any(marker in corpus for marker in ("backend", "fastapi", "api")):
            return "Backend Implementation Project"

        return "Project Evidence"

    def _project_role_from_achievement(self, achievement: dict[str, Any]) -> str:
        corpus = self._achievement_semantic_corpus(achievement)

        if any(marker in corpus for marker in ("computer vision", "cv", "изображен", "video", "видео")):
            return "Visual Data Processing Evidence"

        if any(marker in corpus for marker in ("workflow orchestration", "ai workflow", "pipeline")):
            return "Workflow Implementation Evidence"

        if any(marker in corpus for marker in ("fastapi", "backend", "api")):
            return "Backend/API Implementation Evidence"

        if any(marker in corpus for marker in ("analytics", "data pipeline", "аналит")):
            return "Analytics Evidence"

        return "Project Evidence"

    def _project_bullets_from_achievement(
        self,
        achievement: dict[str, Any],
    ) -> list[str]:
        # Legacy marker: existing domain-specific synthesis must not be extended.
        corpus = self._achievement_semantic_corpus(achievement)
        bullets: list[str] = []

        if "computer vision" in corpus or "мониторинг" in corpus or "quality control" in corpus:
            bullets.append(self._computer_vision_impact_bullet(corpus))
        if "analytics" in corpus or "аналит" in corpus:
            bullets.append(
                "Построил аналитический pipeline для выявления прикладных сигналов "
                "и поддержки решений"
            )
        if "workflow orchestration" in corpus or "ai workflow" in corpus:
            bullets.append("Зафиксированы workflow/orchestration implementation signals")
        if "fastapi" in corpus or "backend" in corpus:
            bullets.append("Зафиксированы backend/API implementation signals")
        if any(marker in corpus for marker in ("evidence review", "review flow", "evidence-review")):
            bullets.append("Зафиксированы evidence-review implementation signals")
        if any(marker in corpus for marker in ("postgresql", "sqlalchemy", "persistence layer")):
            bullets.append("Зафиксированы persistence-layer implementation signals")
        if any(marker in corpus for marker in ("docker", "redis", "infrastructure")):
            bullets.append("Зафиксированы infrastructure implementation signals")

        narrative = str(achievement.get("narrative") or "").strip()
        if narrative and not bullets:
            bullets.append(self._sentence_to_project_bullet(narrative))

        action = str(achievement.get("action") or "").strip()
        if action and not bullets:
            bullets.append(self._sentence_to_project_bullet(action))

        result = str(achievement.get("metric_text") or achievement.get("result") or "").strip()
        if result:
            bullets.append(f"Зафиксировал результат: {result}")

        return self._dedupe_preserve_order(bullets)[:5]

    def _computer_vision_impact_bullet(self, corpus: str) -> str:
        if any(
            marker in corpus
            for marker in (
                "computer vision",
                "cv",
                "изображен",
                "video",
                "видео",
            )
        ):
            return (
                "Реализовал обработку изображений и видео "
                "для прикладных задач мониторинга и контроля"
            )

        if any(marker in corpus for marker in ("безопас", "safety", "security")):
            return (
                "Реализовал pipeline прикладного мониторинга "
                "с использованием AI/CV компонентов"
            )

        return (
            "Реализовал AI/CV pipeline "
            "для обработки визуальных данных"
        )

    def _achievement_semantic_corpus(self, achievement: dict[str, Any]) -> str:
        return " ".join(
            [
                str(achievement.get("title") or ""),
                str(achievement.get("task") or ""),
                str(achievement.get("action") or ""),
                str(achievement.get("result") or ""),
                str(achievement.get("metric_text") or ""),
                str(achievement.get("narrative") or ""),
                str(achievement.get("reason") or ""),
                " ".join(str(skill) for skill in (achievement.get("skills") or [])),
            ]
        ).lower()

    def _sentence_to_project_bullet(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip(" .;-–—•")
        if not cleaned:
            return "Описал проектный вклад на основе подтверждённых фактов"

        first_word = cleaned.split(" ", 1)[0].lower()
        if first_word in {"разработал", "реализовал", "спроектировал", "интегрировал", "построил"}:
            return cleaned
        return f"Реализовал {cleaned}"

    def _balance_ranked_evidence_selection(
        self,
        *,
        ranked_evidence: list[dict[str, Any]],
        evidence_by_id: dict[str, dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        selected_ids: set[str] = set()
        bucket_counts: dict[str, int] = {}

        for bucket, bucket_limit in EVIDENCE_DIVERSITY_BUCKET_LIMITS.items():
            while bucket_counts.get(bucket, 0) < bucket_limit and len(selected) < limit:
                item = self._first_ranked_evidence_for_bucket(
                    ranked_evidence=ranked_evidence,
                    evidence_by_id=evidence_by_id,
                    bucket=bucket,
                    excluded_ids=selected_ids,
                )
                if item is None:
                    break
                selected.append(item)
                bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
                evidence_id = str(item.get("evidence_id") or "").strip()
                if evidence_id:
                    selected_ids.add(evidence_id)
                if len(selected) >= limit:
                    return selected

        for item in ranked_evidence:
            evidence_id = str(item.get("evidence_id") or "").strip()
            if evidence_id and evidence_id in selected_ids:
                continue
            snippet = evidence_by_id.get(evidence_id, item)
            bucket = self._evidence_diversity_bucket(snippet)
            bucket_limit = EVIDENCE_DIVERSITY_BUCKET_LIMITS.get(bucket, 1)
            if bucket_counts.get(bucket, 0) >= bucket_limit:
                continue
            selected.append(item)
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
            if evidence_id:
                selected_ids.add(evidence_id)
            if len(selected) >= limit:
                break

        return selected

    def _first_ranked_evidence_for_bucket(
        self,
        *,
        ranked_evidence: list[dict[str, Any]],
        evidence_by_id: dict[str, dict[str, Any]],
        bucket: str,
        excluded_ids: set[str],
    ) -> dict[str, Any] | None:
        for item in ranked_evidence:
            evidence_id = str(item.get("evidence_id") or "").strip()
            if evidence_id and evidence_id in excluded_ids:
                continue
            snippet = evidence_by_id.get(evidence_id, item)
            if self._evidence_diversity_bucket(snippet) == bucket:
                return item
        return None

    def _evidence_diversity_bucket(self, evidence: dict[str, Any]) -> str:
        category = self._achievement_category_from_evidence(evidence)
        if category in {"github_architecture", "backend_project", "architecture_evidence"}:
            return "backend"
        if category == "ai_workflow":
            return "ai_workflow"
        if category in {"automation_project", "automation", "prompt_engineering", "ai_project"}:
            return "automation"
        if category == "computer_vision":
            return "computer_vision"
        if category == "analytics_project":
            return "analytics"
        return "automation"

    def _achievement_category_from_evidence(self, evidence: dict[str, Any]) -> str:
        star_summary = dict(evidence.get("star_summary") or {})
        raw_category = str(
            evidence.get("category")
            or star_summary.get("category")
            or star_summary.get("type")
            or ""
        ).strip().lower()
        if raw_category in ACHIEVEMENT_CATEGORIES:
            return raw_category
        if raw_category == "architecture_evidence":
            return "github_architecture"
        if raw_category in {"ai_workflow", "workflow_orchestration"}:
            return "ai_workflow"
        if raw_category in {"automation", "prompt_engineering", "ai_project"}:
            return "automation_project"

        text = " ".join(
            [
                str(evidence.get("title") or ""),
                str(evidence.get("snippet_text") or ""),
                " ".join(str(skill) for skill in (evidence.get("skills") or [])),
            ]
        ).lower()
        if any(marker in text for marker in ("computer vision", "monitoring", "изображ", "видео")):
            return "computer_vision"
        if any(marker in text for marker in ("analytics", "data analysis", "аналит")):
            return "analytics_project"
        if any(marker in text for marker in ("fastapi", "backend", "architecture", "sqlalchemy")):
            return "backend_project"
        if any(marker in text for marker in ("workflow orchestration", "ai workflow", "orchestration")):
            return "ai_workflow"
        if any(marker in text for marker in ("automation", "openai", "telegram", "llm")):
            return "automation_project"
        return raw_category or "project"

    def _category_bucket(self, category: str) -> str:
        if category in ENGINEERING_ACHIEVEMENT_CATEGORIES:
            return "engineering"
        if category in AUTOMATION_ACHIEVEMENT_CATEGORIES:
            return "automation"
        if category in BUSINESS_DOMAIN_ACHIEVEMENT_CATEGORIES:
            return "business_domain"
        return "business_domain"

    def _provenance_label_from_evidence(self, evidence: dict[str, Any]) -> str:
        category = self._achievement_category_from_evidence(evidence)
        title = str(evidence.get("title") or "").strip()
        labels = {
            "github_architecture": "GitHub architecture evidence",
            "automation_project": "AI workflow orchestration",
            "computer_vision": "Computer vision project",
            "analytics_project": "Analytics project",
            "backend_project": "Backend project",
        }
        if category in labels:
            return labels[category]
        return title or "Resume achievement"

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
            bullets.append(
                f"Профессиональный фокус: {self._normalize_profile_focus(profile.headline)}."
            )

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
                "Подтверждённый профессиональный опыт для возможного использования в отклике: "
                f"{ensure_selected_achievement(selected_achievements[0]).title}."
            )

        return bullets[:4]

    def _normalize_profile_focus(self, value: str) -> str:
        terms = [
            self._normalize_display_skill(part)
            for part in self._split_skill_text(value)
        ]
        normalized_terms = {
            term.strip().lower()
            for term in terms
            if term and term.strip().lower() not in LOW_SIGNAL_SKILLS
        }
        corpus = " ".join(sorted(normalized_terms))

        return ", ".join(self._dedupe_preserve_order(terms)) or value.strip()

    def _build_ats_tailoring_sections(
        self,
        *,
        vacancy_title: str,
        matched_keywords: list[str],
        missing_keywords: list[str],
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
        evidence_snippets: list[dict[str, Any]],
        experience_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        relevant_to_vacancy = self._build_relevant_to_vacancy(
            matched_keywords=matched_keywords,
            selected_skills=selected_skills,
            evidence_snippets=evidence_snippets,
        )

        selected_skill_keys = {
            self._normalize_display_skill(skill).casefold()
            for skill in selected_skills
        }
        relevant_keys = {
            self._normalize_display_skill(item).casefold()
            for item in relevant_to_vacancy
        }

        if relevant_keys and relevant_keys.issubset(selected_skill_keys):
            relevant_to_vacancy = []

        vacancy_aligned_summary = self._build_vacancy_aligned_summary(
            vacancy_title=vacancy_title,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            experience_items=experience_items,
        )
        competency_mapping = self._build_competency_mapping(
            relevant_to_vacancy=relevant_to_vacancy,
            evidence_snippets=evidence_snippets,
            missing_keywords=missing_keywords,
            selected_achievements=selected_achievements,
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
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
        experience_items: list[dict[str, Any]],
    ) -> str:
        role = re.sub(
            r"\s+вакансия\s*$",
            "",
            vacancy_title.strip(),
            flags=re.IGNORECASE,
        ).strip() or "кандидат"

        experience_text = " ".join(
            str(item.get("description_raw") or "")
            for item in experience_items[:2]
        )

        experience_text = re.sub(r"\s+", " ", experience_text).strip()

        focus_phrases: list[str] = []

        rules = [
            ("ведения первичной документации", ("первичн", "документац")),
            ("работы с актами, счетами и накладными", ("акт", "счет", "счёт", "накладн")),
            ("сверки взаиморасчётов с контрагентами", ("сверк", "контрагент")),
            ("подготовки платёжных поручений", ("платеж", "платёж")),
            ("работы в 1С:Бухгалтерия и Excel", ("1с", "excel")),
            ("подготовки данных для бухгалтерской и налоговой отчётности", ("отчётност", "отчетност", "налог")),
        ]

        lowered_experience = experience_text.lower()

        for label, markers in rules:
            if any(marker in lowered_experience for marker in markers):
                focus_phrases.append(label)

        focus_phrases = self._dedupe_preserve_order(focus_phrases)

        if not focus_phrases:
            focus_phrases = selected_skills[:3]

        focus = ", ".join(focus_phrases[:3]) if focus_phrases else "релевантных профессиональных задач"
        achievement_titles = [
            str(item.get("title") or "").strip()
            for item in selected_achievements[:2]
            if str(item.get("title") or "").strip()
        ]

        summary = f"{role} с опытом {focus}."
        if achievement_titles:
            summary += (
                " Среди подтверждённых результатов: "
                + "; ".join(achievement_titles)
                + "."
            )
        return summary

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

    def _looks_like_ai_or_tech_context(self, text: str) -> bool:
        corpus = text.lower()
        return any(
            marker in corpus
            for marker in (
                "python",
                "fastapi",
                "backend",
                "api",
                "llm",
                "openai",
                "chatgpt",
                "prompt",
                "machine learning",
                "computer vision",
                "искусственный интеллект",
            )
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
                display = self._normalize_display_skill(normalized)
                if display.lower() not in LOW_SIGNAL_SKILLS:
                    candidates.append(self._display_relevance_label(display))

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
        if self._looks_like_ai_or_tech_context(
            " ".join([*matched_keywords, *selected_skills, evidence_text])
        ):
            semantic_rules = [
                ("Prompt engineering", ("prompt", "prompt engineering", "промпт")),
                ("AI tooling", ("llm", "chatgpt", "ai interaction", "ai tooling")),
                ("Workflow automation", ("automation", "workflow", "no-code", "nocode")),
                ("Python", ("python",)),
                ("AI/LLM tooling", ("llm", "openai", "chatgpt", "искусственный интеллект")),
            ]
        else:
            semantic_rules = []

        for label, markers in semantic_rules:
            if any(marker in evidence_text for marker in markers):
                candidates.append(label)

        for skill in selected_skills:
            display = self._normalize_display_skill(skill)
            if display and display.lower() not in LOW_SIGNAL_SKILLS:
                candidates.append(self._display_relevance_label(display))

        return self._dedupe_preserve_order(candidates)[:8]

    def _build_competency_mapping(
        self,
        *,
        relevant_to_vacancy: list[str],
        evidence_snippets: list[dict[str, Any]],
        missing_keywords: list[str],
        selected_achievements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        mapping: list[dict[str, Any]] = []
        selected_titles = {
            str(item.get("title") or "").strip().lower()
            for item in selected_achievements
            if str(item.get("title") or "").strip()
        }
        relevant_titles = {str(item).strip().lower() for item in relevant_to_vacancy if str(item).strip()}

        for competency in relevant_to_vacancy:
            evidence = self._find_best_evidence_for_competency(
                competency,
                evidence_snippets,
            )
            evidence_title = str(evidence.get("title") or "").strip().lower() if evidence else ""
            if (
                evidence
                and selected_titles
                and evidence_title not in selected_titles
                and evidence_title not in relevant_titles
            ):
                continue

            mapping.append(
                {
                    "competency": competency,
                    "coverage": "supported" if evidence else "profile_keyword",
                    "evidence_id": evidence.get("id") if evidence else None,
                    "evidence_title": evidence.get("title") if evidence else None,
                    "evidence": self._render_competency_evidence(
                        competency=competency,
                        evidence=evidence,
                    ),
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
                    "evidence": (
                        "Нужно подтвердить практический опыт или добавить проектный пример"
                    ),
                    "fact_status": "needs_review",
                }
            )

        deduped_mapping: list[dict[str, Any]] = []
        seen_signatures: set[tuple[str, str | None]] = set()

        for item in mapping:
            competency = str(item.get("competency") or "").strip()
            evidence_id = item.get("evidence_id")
            evidence_text = str(item.get("evidence") or "").strip()

            signature = (
                evidence_text.lower() if evidence_text else competency.lower(),
                str(evidence_id) if evidence_id else None,
            )

            if signature in seen_signatures:
                continue

            seen_signatures.add(signature)
            deduped_mapping.append(item)

        return deduped_mapping

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
        competency_markers = self._competency_specific_markers(competency)
        requires_direct_evidence = self._requires_direct_competency_evidence(
            competency
        )
        best: tuple[int, dict[str, Any]] | None = None
        fallback_best: tuple[int, dict[str, Any]] | None = None
        for snippet in evidence_snippets:
            text = " ".join(
                [
                    str(snippet.get("title") or ""),
                    str(snippet.get("snippet_text") or ""),
                    " ".join(str(skill) for skill in snippet.get("skills") or []),
                ]
            ).lower()
            score = sum(1 for token in competency_tokens if token in text)
            marker_score = sum(
                1 for marker in competency_markers if marker in text
            )
            if competency_markers and marker_score <= 0:
                if requires_direct_evidence:
                    continue
                if score > 0 and (
                    fallback_best is None or score > fallback_best[0]
                ):
                    fallback_best = (score, snippet)
                continue

            score += marker_score * 4
            score += self._category_competency_bonus(
                competency=competency,
                evidence=snippet,
            )
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, snippet)
        if best:
            return best[1]
        if requires_direct_evidence:
            return None
        return fallback_best[1] if fallback_best else None

    def _competency_specific_markers(self, competency: str) -> set[str]:
        normalized = competency.strip().lower().replace("_", " ")
        marker_map = {
            "git": {"git", "github", "version control", "repository"},
            "version control": {"git", "github", "version control", "repository"},
            "fastapi": {"fastapi", "api", "backend", "apirouter"},
            "backend": {"backend", "fastapi", "api", "persistence"},
            "docker": {"docker", "dockerfile", "docker-compose", "infrastructure"},
            "pytest": {"pytest", "tests", "testclient", "testing"},
            "testing": {"pytest", "tests", "testclient", "testing"},
            "postgresql": {"postgresql", "postgres", "sqlalchemy", "persistence"},
            "sqlalchemy": {"sqlalchemy", "postgresql", "persistence"},
            "workflow automation": {"workflow", "automation", "pipeline"},
            "prompt engineering": {"prompt", "prompt engineering"},
        }
        for key, markers in marker_map.items():
            if key in normalized:
                return markers
        if self._is_generic_ai_competency(normalized):
            return {
                "artificial intelligence",
                "искусственный интеллект",
                "machine learning",
                "computer vision",
                "нейросети",
                "ai system",
                "ai monitoring",
                "ai/cv",
            }
        return set()

    def _requires_direct_competency_evidence(self, competency: str) -> bool:
        normalized = competency.strip().lower().replace("_", " ")
        return "git" in normalized or self._is_generic_ai_competency(normalized)

    def _is_generic_ai_competency(self, normalized_competency: str) -> bool:
        return normalized_competency in {
            "ai",
            "искусственный интеллект",
            "artificial intelligence",
        }

    def _category_competency_bonus(
        self,
        *,
        competency: str,
        evidence: dict[str, Any],
    ) -> int:
        normalized = competency.strip().lower()
        bucket = self._evidence_diversity_bucket(evidence)
        if any(marker in normalized for marker in ("fastapi", "backend", "api")):
            return 3 if bucket == "backend" else 0
        if any(marker in normalized for marker in ("docker", "infra")):
            return 3 if bucket == "backend" else 0
        if any(marker in normalized for marker in ("pytest", "testing", "test")):
            text = " ".join(
                [
                    str(evidence.get("title") or ""),
                    str(evidence.get("snippet_text") or ""),
                    " ".join(str(skill) for skill in evidence.get("skills") or []),
                ]
            ).lower()
            return 4 if any(marker in text for marker in ("pytest", "testing", "testclient")) else 0
        if "workflow" in normalized:
            return 3 if bucket in {"ai_workflow", "automation"} else 0
        return 0

    def _render_competency_evidence(
        self,
        *,
        competency: str,
        evidence: dict[str, Any] | None,
    ) -> str:
        competency_lower = competency.lower()
        evidence_text = ""
        if evidence:
            evidence_text = " ".join(
                [
                    str(evidence.get("title") or ""),
                    str(evidence.get("snippet_text") or ""),
                    " ".join(str(skill) for skill in (evidence.get("skills") or [])),
                ]
            ).lower()
        corpus = f"{competency_lower} {evidence_text}"

        if "git" in competency_lower:
            if evidence:
                return "Использование Git/repository workflow в проектной разработке"
            return "Использование Git в проектной разработке требует отдельного подтверждения"
        if self._is_generic_ai_competency(competency_lower.strip().replace("_", " ")):
            if evidence:
                return "Применение AI/ML подходов в подтверждённом проектном контексте"
            return "Практический опыт с искусственным интеллектом требует отдельного подтверждения"

        if "prompt" in competency_lower:
            return (
                "Практическое применение prompt/workflow подходов в подтверждённом контексте"
            )
        if "workflow automation" in competency_lower or "automation" in competency_lower:
            return (
                "Практическое применение workflow automation в подтверждённом контексте"
            )
        if any(marker in competency_lower for marker in ("ai tooling", "llm", "chatgpt", "openai")):
            return "Интеграция LLM/OpenAI tooling в прикладной workflow"
        if any(marker in competency_lower for marker in ("python", "fastapi", "backend")):
            return "Практический опыт разработки или автоматизации на Python"

        if "prompt" in corpus:
            return (
                "Практическое применение prompt/workflow подходов в подтверждённом контексте"
            )
        if "workflow automation" in corpus or "automation" in corpus or "workflow" in corpus:
            return (
                "Практическое применение workflow automation в подтверждённом контексте"
            )
        if any(marker in corpus for marker in ("ai tooling", "llm", "chatgpt", "openai")):
            return "Интеграция LLM/OpenAI tooling в прикладной workflow"
        if any(marker in corpus for marker in ("python", "fastapi", "backend")):
            return "Практический опыт разработки или автоматизации на Python"
        if any(marker in corpus for marker in ("analytics", "analysis", "data")):
            return "Обработка данных и извлечение сигналов для принятия решений"

        if evidence:
            snippet = str(evidence.get("snippet_text") or "").strip()

            if snippet:
                snippet = re.sub(r"\s+", " ", snippet)

                if len(snippet) > 140:
                    snippet = snippet[:140].rsplit(" ", 1)[0] + "..."

                return snippet

        return "Практический опыт требует дополнительного подтверждения"

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
            "python": "Python",
        }
        return known.get(normalized.lower(), normalized)

    def _build_experience_items(self, profile) -> list[dict]:
        items: list[dict] = []

        for exp in profile.experiences[:5]:
            item = {
                "company": exp.company,
                "role": exp.role,
                "period": self._format_period(exp.start_date, exp.end_date),
                "description_raw": self._normalize_experience_description(
                    exp.description_raw
                ),
            }

            if self._looks_like_low_confidence_experience_item(item):
                continue

            items.append(item)

        return items

    def _normalize_experience_description(self, value: str | None) -> str | None:
        if not value:
            return None

        lines = [
            re.sub(r"[ \t]+", " ", line).strip(" .;-–—•")
            for line in str(value).splitlines()
        ]

        lines = [line for line in lines if line]

        if not lines:
            return None

        text = "\n".join(lines)

        for boundary in EXPERIENCE_RESPONSIBILITY_BOUNDARIES:
            text = re.sub(
                rf"(?<!^)\s+({re.escape(boundary)})",
                r"\n\1",
                text,
                flags=re.IGNORECASE,
            )

        parts = [
            part.strip(" .;-–—•")
            for part in re.split(r"\s+-\s+|[;•]+", text)
            if part.strip(" .;-–—•")
        ]

        if len(parts) <= 1:
            return text

        return "\n".join(self._dedupe_preserve_order(parts))

    def _looks_like_low_confidence_experience_item(self, item: dict) -> bool:
        combined = " ".join(
            str(item.get(field) or "")
            for field in ("company", "role", "description_raw")
        )
        return self.legacy_recovery_service.looks_like_legacy_low_confidence_experience_noise(
            combined
        )

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
