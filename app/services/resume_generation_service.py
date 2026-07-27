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
from app.domain.evidence_alignment import (
    humanize_experience_phrase,
    score_alignment_item,
)
from app.domain.text_normalization import (
    clean_vacancy_title,
    dedupe_subsumed_phrases,
    humanize_vacancy_requirement_phrase,
    make_user_facing_evidence_phrase,
    strip_emoji_deep,
)
from app.services.document_compat import (
    achievement_to_dict,
    ensure_keyword_set,
    ensure_selected_achievement,
)
from app.services.document_evidence_guards import filter_user_facing_achievements
from app.services.document_feedback import build_claim, build_warning
from app.services.document_evaluator import _extract_metrics
from app.services.document_builders import build_resume_content
from app.services.document_evidence_selection_service import DocumentEvidenceSelectionService
from app.services.evidence_bank_service import EVIDENCE_BANK_SOURCE_TYPES, EvidenceBankService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.evidence_selection_service import EvidenceSelectionService
from app.services.evidence_strength_ranker import EvidenceStrengthRanker
from app.services.profile_structuring_service import ProfileStructuringService
from app.services.legacy_resume_recovery_service import LegacyResumeRecoveryService
from app.services.semantic_requirement_matcher import SemanticRequirementMatcher
from app.services.semantic_summary_ranker import SemanticSummaryRanker
from app.services.resume_renderer import render_resume
from app.services.vacancy_fit_context_service import VacancyFitContextService
from app.services.core_service_policy import LEGACY_CANDIDATE_SPECIFIC_HEURISTIC
from app.services.text_polish.achievement_verbalizer import AchievementVerbalizer
from app.services.text_polish.humanizer import (
    format_summary_focus_phrases,
    humanize_resume_role,
)
from app.services.text_polish.narrative_builder import NarrativeBuilder


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
    "Adobe Photoshop",
    "Adobe Illustrator",
    "Figma",
    "CorelDRAW",
    "Полиграфический дизайн",
    "Брендинг",
    "Подготовка макетов к печати",
    "Визуальная коммуникация",
    "Типографика",
]

GENERIC_MULTIWORD_SKILLS = [
    *KNOWN_MULTIWORD_SKILLS,
    "Медицинская документация",
    "Клиническая диагностика",
    "Электронные медицинские системы",
    "Амбулаторный прием",
    "Амбулаторный приём",
    "Экстренная медицинская помощь",
    "Предрейсовые осмотры",
    "Послерейсовые осмотры",
    "Медицинское освидетельствование",
]

EXPERIENCE_RESPONSIBILITY_BOUNDARIES = [
    "Подготовка договоров",
    "Судебное сопровождение",
    "Консультирование клиентов",
    "Организация складских процессов",
    "Управление отделом снабжения",
    "Планирование бюджета снабжения",
    "Контроль логистических процессов",
    "Ведение переговоров с поставщиками",
    "Контроль исполнения договорных обязательств",
    "Организация закупочной деятельности",
    "Управление складскими запасами",
    "Диагностика пациентов",
    "Назначение лечения",
    "Ведение медицинской документации",
    "Координация маршрутизации пациентов",
    "Претензионная работа",
    "Разработка рекламных материалов",
    "Создание фирменного стиля",
    "Разработка визуальных концепций",
    "Создание контента для социальных сетей",
    "Подготовка макетов к печати",
]

CAPABILITY_PHRASES = [
    "Закупочная деятельность",
    "Материально-техническое обеспечение",
    "Управление складскими запасами",
    "Бюджетирование",
    "Договорная работа",
    "Ведение переговоров",
    "Управление поставщиками",
    "Контроль поставок",
    "Претензионная работа",
    "Логистика",
]

CAPABILITY_PHRASE_MARKERS = {
    "Закупочная деятельность": (
        r"закуп",
        r"(?<!водо)снабжен",
        r"мто",
    ),
    "Материально-техническое обеспечение": (
        r"материально[-\s]?техническ",
        r"\bмто\b",
    ),
    "Управление складскими запасами": (
        r"складск",
        r"запас",
        r"остат",
    ),
    "Бюджетирование": (
        r"бюджет",
        r"бизнес-план",
        r"планирован",
    ),
    "Договорная работа": (
        r"договор",
        r"спецификац",
        r"доп\.?\s*соглаш",
    ),
    "Ведение переговоров": (
        r"переговор",
        r"переписк",
        r"поставщик",
        r"заказчик",
    ),
    "Управление поставщиками": (
        r"поставщик",
        r"поставк",
    ),
    "Контроль поставок": (
        r"контроль постав",
        r"контроль логист",
        r"сроки постав",
    ),
    "Претензионная работа": (
        r"претензи",
        r"нарекан",
        r"недостатк",
    ),
    "Логистика": (
        r"логист",
        r"достав",
        r"перевоз",
    ),
}

BUSINESS_TOOL_SKILL_MARKERS = {
    "excel",
    "word",
    "1с",
    "1c",
}

DISPLAY_NORMALIZATION_MAP = {
    "devloher": "developer",
    "chatgpt": "ChatGPT",
    "llm": "LLM",
    "ai": "AI",
    "openai": "OpenAI",
    "ai workflow": "AI Workflow",
    "no-code": "No-code",
    "1c": "1С",
    "1с": "1С",
    "1c erp": "1С ERP",
    "1с erp": "1С ERP",
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
        self.achievement_verbalizer = AchievementVerbalizer()
        self.narrative_builder = NarrativeBuilder()
        self.semantic_matcher = SemanticRequirementMatcher()
        self.evidence_strength_ranker = EvidenceStrengthRanker()
        self.semantic_summary_ranker = SemanticSummaryRanker(
            evidence_strength_ranker=self.evidence_strength_ranker,
        )
        self.document_evidence_selection_service = DocumentEvidenceSelectionService()

    async def generate_resume(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        user_id: UUID,
        use_ai_enhancement: bool = False,
        market: str | None = None,
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

        # Этап 7: явный market из запроса имеет приоритет, иначе профиль, иначе RU.
        resolved_market = market or getattr(profile, "market", None) or "ru"

        latest_extraction = await self.file_extraction_repository.get_latest_for_active_source_file_kind(
            session,
            user_id,
            file_kind="resume",
        )
        contact_info = self._extract_contact_info(
            latest_extraction.extracted_text if latest_extraction else ""
        )

        experience_items = self._build_experience_items(profile)

        raw_skills = self._extract_skills_from_profile_or_raw_text(
            profile_summary=profile.summary,
            raw_text=latest_extraction.extracted_text if latest_extraction else "",
        )
        capability_skills = self._extract_capability_skills_from_experience(
            experience_items=experience_items,
        )
        raw_skills = self._dedupe_preserve_order([*capability_skills, *raw_skills])

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

        tailoring = self._build_ats_tailoring_sections(
            vacancy_title=vacancy.title,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            evidence_snippets=evidence_snippets,
            experience_items=experience_items,
        )
        document_evidence_selection = (
            self.document_evidence_selection_service.build_from_document_parts(
                selected_achievements=selected_achievements,
                selected_evidence_ids=selected_evidence_ids,
                evidence_selection_reason=selected_evidence_reason,
                vacancy_evidence_alignment=tailoring["vacancy_evidence_alignment"],
                top_alignment_evidence=tailoring["top_alignment_evidence"],
            )
        )
        user_facing_selected_achievements = filter_user_facing_achievements(
            document_evidence_selection.selected_achievements
        )

        vacancy_fit_context = VacancyFitContextService().build(
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            selected_skills=selected_skills,
            evidence_snippets=evidence_snippets,
            selected_achievements=selected_achievements,
        )
        vacancy_fit_narrative = vacancy_fit_context["vacancy_fit_narrative"]

        summary_bullets = self._build_summary_bullets(
            profile=profile,
            vacancy_title=vacancy.title,
            selected_skills=selected_skills,
            selected_achievements=user_facing_selected_achievements,
            matched_keywords=matched_keywords,
            top_alignment_evidence=tailoring["top_alignment_evidence"],
            vacancy_aligned_summary=tailoring["vacancy_aligned_summary"],
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
                market=resolved_market,
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

        user_facing_selected_achievements = self.narrative_builder.add_project_narratives(
            user_facing_selected_achievements
        )

        project_sections: list[dict[str, Any]] = []
        if not experience_items:
            project_sections = self.narrative_builder.build_project_sections(
                user_facing_selected_achievements
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
            vacancy_fit_narrative=vacancy_fit_narrative,
            vacancy_aligned_summary=tailoring["vacancy_aligned_summary"],
            vacancy_evidence_alignment=tailoring["vacancy_evidence_alignment"],
            top_alignment_evidence=tailoring["top_alignment_evidence"],
            competency_mapping=tailoring["competency_mapping"],
            relevant_to_vacancy=tailoring["relevant_to_vacancy"],
            project_sections=project_sections,
            summary_bullets=summary_bullets,
            skills=selected_skills,
            experience=experience_items,
            education=education_items,
            courses=course_items,
            internships=internship_items,
            selected_achievements=user_facing_selected_achievements,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            matched_requirements=analysis.strengths_json,
            gap_requirements=analysis.gaps_json,
            claims_needing_confirmation=claims_needing_confirmation,
            selection_rationale=selection_rationale,
            warnings=warnings,
            source="hybrid" if use_ai_enhancement else "extracted",
            based_on_achievements=[
                item["id"]
                for item in document_evidence_selection.selected_achievements
                if item.get("id")
            ],
            selected_achievement_ids=[
                item["id"]
                for item in document_evidence_selection.selected_achievements
                if item.get("id")
            ],
            based_on_analysis_id=str(analysis.id),
            selected_evidence_ids=document_evidence_selection.selected_evidence_ids,
            evidence_selection_reason=(
                document_evidence_selection.evidence_selection_reason
                or selection_rationale
            ),
            confidence=confidence_assessment.confidence,
            confidence_level=confidence_assessment.confidence_level.value,
            generation_prompt_version=(
                "resume_tailor_v1" if use_ai_enhancement else None
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
            market=resolved_market,
        )

        # LLM-NLG может вставить эмодзи в поля (target_position/summary) —
        # юзер явно просил «эмодзи нигде не использовать». Граница загрузки
        # (strip_emoji) покрывает импорт; здесь покрываем LLM-вывод, чтобы
        # content_json и rendered_text были чистыми.
        content_json = strip_emoji_deep(content_json)
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
        profile_skills = self._split_skill_text(profile_summary or "")
        if profile_skills:
            return profile_skills

        return self._extract_skills_from_raw_text(raw_text)

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

        for skill in GENERIC_MULTIWORD_SKILLS:
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
            "Навыки:",
            "НАВЫКИ:",
            "Skills:",
            "SKILLS:",
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
                r"^(ПРОФЕССИОНАЛЬНЫЕ\s+НАВЫКИ(?:\s+И\s+\w+)?|НАВЫКИ(?:\s+И\s+\w+)?|КОМПЕТЕНЦИИ|SKILLS)\s*[:：-]?\s*(.*)$",
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

    def _extract_capability_skills_from_experience(
        self,
        experience_items: list[dict[str, Any]],
    ) -> list[str]:
        capabilities: list[str] = []

        for item in experience_items or []:
            search_text = self._build_experience_search_text(item).casefold()
            if not search_text:
                continue

            for phrase in CAPABILITY_PHRASES:
                patterns = CAPABILITY_PHRASE_MARKERS.get(phrase, ())
                if any(re.search(pattern, search_text) for pattern in patterns):
                    capabilities.append(phrase)

        return self._dedupe_preserve_order(capabilities)

    def _build_experience_search_text(self, item: dict[str, Any]) -> str:
        chunks: list[str] = []

        for key in (
            "role",
            "position",
            "title",
            "company",
            "description_raw",
            "description",
            "summary",
        ):
            value = item.get(key)
            if value:
                chunks.append(str(value))

        for key in (
            "responsibilities",
            "achievements",
            "bullets",
            "items",
        ):
            value = item.get(key)
            if isinstance(value, list):
                chunks.extend(str(part) for part in value if part)

        return re.sub(r"\s+", " ", " ".join(chunks)).strip()

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

        normalized = self._dedupe_preserve_order(normalized)
        if "Складская логистика" in normalized and "Логистика" in normalized:
            normalized = [skill for skill in normalized if skill != "Логистика"]
        if self._has_design_context(normalized, matched_keywords):
            normalized = self._rank_design_skills(
                normalized,
                matched_keywords=matched_keywords,
            )
        if any(skill in CAPABILITY_PHRASES for skill in normalized):
            normalized = self._rank_business_capability_skills(
                normalized,
                matched_keywords=matched_keywords,
            )
        return normalized[:10]

    def _has_design_context(self, skills: list[str], matched_keywords: list[str]) -> bool:
        corpus = " ".join([*skills, *matched_keywords]).casefold()
        return any(
            marker in corpus
            for marker in (
                "photoshop",
                "illustrator",
                "figma",
                "coreldraw",
                "брендинг",
                "дизайн",
                "типограф",
                "макет",
            )
        )

    def _rank_design_skills(
        self,
        skills: list[str],
        *,
        matched_keywords: list[str],
    ) -> list[str]:
        matched_keys = {
            self._normalize_display_skill(keyword).strip().casefold()
            for keyword in matched_keywords
            if str(keyword).strip()
        }
        priority = {
            "adobe photoshop": 0,
            "adobe illustrator": 1,
            "figma": 2,
            "coreldraw": 3,
            "полиграфический дизайн": 4,
            "брендинг": 5,
            "подготовка макетов к печати": 6,
            "визуальная коммуникация": 7,
            "типографика": 8,
        }

        def rank_key(item: tuple[int, str]) -> tuple[int, int, int]:
            index, skill = item
            normalized = self._normalize_display_skill(skill).strip().casefold()
            if normalized in priority:
                return (0, priority[normalized], index)
            if normalized in matched_keys:
                return (1, 0, index)
            return (2, 0, index)

        return [
            skill
            for _, skill in sorted(enumerate(skills), key=rank_key)
        ]

    def _rank_business_capability_skills(
        self,
        skills: list[str],
        *,
        matched_keywords: list[str],
    ) -> list[str]:
        matched_keys = {
            self._normalize_display_skill(keyword).strip().casefold()
            for keyword in matched_keywords
            if str(keyword).strip()
        }
        capability_order = {
            phrase.casefold(): index
            for index, phrase in enumerate(CAPABILITY_PHRASES)
        }

        def rank_key(item: tuple[int, str]) -> tuple[int, int, int, int]:
            index, skill = item
            normalized = self._normalize_display_skill(skill).strip().casefold()
            if normalized in capability_order:
                return (0, capability_order[normalized], 0, index)
            if normalized in matched_keys and not self._is_business_tool_skill(skill):
                return (1, 0, 0, index)
            if self._is_business_tool_skill(skill):
                return (3, 0, 0, index)
            return (2, 0, 0, index)

        return [
            skill
            for _, skill in sorted(enumerate(skills), key=rank_key)
        ]

    def _is_business_tool_skill(self, skill: str) -> bool:
        normalized = self._normalize_display_skill(skill).strip().casefold()
        return any(marker in normalized for marker in BUSINESS_TOOL_SKILL_MARKERS)

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

        if key in {"графические редакторы", "графических редакторов"}:
            return raw in {"adobe photoshop", "adobe illustrator", "coreldraw", "figma"}

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
            "target_role": clean_vacancy_title(vacancy_title),
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
        top_alignment_evidence: list[dict[str, Any]],
        vacancy_aligned_summary: str,
    ) -> list[str]:
        bullets: list[str] = []
        clean_title = clean_vacancy_title(vacancy_title)

        if profile.headline:
            bullets.append(
                f"Профессиональный фокус: {self._normalize_profile_focus(profile.headline)}."
            )

        alignment_phrases = [
            str(item.get("summary_phrase") or "").strip()
            for item in top_alignment_evidence
            if str(item.get("summary_phrase") or "").strip()
        ]
        alignment_phrases = self._dedupe_preserve_order(alignment_phrases)

        if alignment_phrases:
            bullets.append(
                "Ключевой профиль опыта: "
                + ", ".join(alignment_phrases[:3])
                + "."
            )
        elif vacancy_aligned_summary:
            bullets.append(vacancy_aligned_summary)
        elif matched_keywords and not alignment_phrases:
            bullets.append(
                f"Опыт, релевантный позиции {clean_title}: "
                f"{', '.join(matched_keywords[:6])}."
            )

        if selected_skills and not alignment_phrases:
            bullets.append(
                f"Дополнительные навыки из резюме: {', '.join(selected_skills[:8])}."
            )

        if selected_achievements:
            bullets.append(
                "Профессиональный результат для отклика: "
                f"{ensure_selected_achievement(selected_achievements[0]).title}."
            )

        return bullets[:4]

    def _normalize_profile_focus(self, value: str) -> str:
        terms = [
            self._normalize_display_skill(part)
            for part in self._split_skill_text(value)
        ]

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

        vacancy_evidence_alignment = self._build_vacancy_evidence_alignment(
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            selected_skills=selected_skills,
            evidence_snippets=evidence_snippets,
            selected_achievements=selected_achievements,
        )
        top_alignment_evidence = self._build_top_alignment_evidence(
            vacancy_evidence_alignment=vacancy_evidence_alignment,
        )
        vacancy_aligned_summary = self._build_vacancy_aligned_summary(
            vacancy_title=vacancy_title,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            experience_items=experience_items,
            vacancy_evidence_alignment=vacancy_evidence_alignment,
            top_alignment_evidence=top_alignment_evidence,
        )
        competency_mapping = self._build_competency_mapping(
            relevant_to_vacancy=relevant_to_vacancy,
            evidence_snippets=evidence_snippets,
            missing_keywords=missing_keywords,
            selected_achievements=selected_achievements,
        )
        return {
            "vacancy_aligned_summary": vacancy_aligned_summary,
            "vacancy_evidence_alignment": vacancy_evidence_alignment,
            "top_alignment_evidence": top_alignment_evidence,
            "competency_mapping": competency_mapping,
            "relevant_to_vacancy": relevant_to_vacancy,
        }

    def _build_vacancy_evidence_alignment(
        self,
        *,
        matched_keywords: list[str],
        missing_keywords: list[str],
        selected_skills: list[str],
        evidence_snippets: list[dict[str, Any]],
        selected_achievements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        requirements = self._dedupe_preserve_order(
            [
                self._display_relevance_label(str(item).strip())
                for item in [*matched_keywords, *missing_keywords]
                if str(item).strip()
            ]
        )
        selected_titles = {
            str(item.get("title") or "").strip().lower()
            for item in selected_achievements
            if str(item.get("title") or "").strip()
        }
        selected_skill_keys = {
            self._normalize_display_skill(skill).strip().lower()
            for skill in selected_skills
            if str(skill).strip()
        }

        alignment: list[dict[str, Any]] = []
        for requirement in requirements:
            evidence = self._find_best_evidence_for_competency(
                requirement,
                evidence_snippets,
            )
            evidence_title = (
                str(evidence.get("title") or "").strip().lower()
                if evidence
                else ""
            )
            requirement_title = str(requirement or "").strip().lower()
            if (
                evidence
                and selected_titles
                and evidence_title not in selected_titles
                and evidence_title != requirement_title
            ):
                evidence = None

            evidence_label = (
                self._render_alignment_evidence_label(evidence)
                if evidence
                else None
            )
            skill_supported = self._requirement_supported_by_skills(
                requirement=requirement,
                selected_skill_keys=selected_skill_keys,
            )
            label_is_fallback = False
            if evidence_label is None and skill_supported:
                evidence_label = humanize_vacancy_requirement_phrase(requirement)
                if evidence_label is None:
                    evidence_label = self._display_relevance_label(requirement)
                label_is_fallback = True

            confidence = (
                "high"
                if evidence_label and not label_is_fallback
                else "medium" if skill_supported else "gap"
            )
            alignment.append(
                {
                    "requirement": requirement,
                    "evidence": evidence_label,
                    "confidence": confidence,
                    "evidence_id": evidence.get("id") if evidence else None,
                    "fact_status": evidence.get("fact_status") if evidence else "needs_review",
                }
            )

        return self._dedupe_vacancy_evidence_alignment(alignment)[:8]

    def _build_top_alignment_evidence(
        self,
        *,
        vacancy_evidence_alignment: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prioritized = []
        for item in vacancy_evidence_alignment:
            confidence = str(item.get("confidence") or "").strip().lower()
            evidence = str(item.get("evidence") or "").strip()
            requirement = str(item.get("requirement") or "").strip()
            if not evidence or confidence not in {"high", "medium"}:
                continue

            user_facing_evidence = make_user_facing_evidence_phrase(evidence)
            summary_phrase = self._alignment_summary_phrase(
                requirement=requirement,
                evidence=user_facing_evidence or requirement,
            )
            summary_phrase = humanize_experience_phrase(summary_phrase)
            if make_user_facing_evidence_phrase(summary_phrase) is None:
                continue

            prioritized.append(
                {
                    "requirement": requirement,
                    "evidence": user_facing_evidence or requirement,
                    "summary_phrase": summary_phrase,
                    "confidence": confidence,
                    "evidence_id": item.get("evidence_id"),
                    "fact_status": item.get("fact_status"),
                }
            )

        prioritized = self._dedupe_top_alignment_evidence(prioritized)
        prioritized = [
            item
            for item in prioritized
            if item.get("summary_phrase")
        ]
        if prioritized:
            phrases = dedupe_subsumed_phrases(
                [str(item.get("summary_phrase") or "") for item in prioritized]
            )
            by_phrase = {
                str(item.get("summary_phrase") or "").strip(): item
                for item in prioritized
            }
            prioritized = [
                by_phrase[phrase]
                for phrase in phrases
                if phrase in by_phrase
            ]

        prioritized = sorted(prioritized, key=score_alignment_item, reverse=True)

        return prioritized[:3]

    def _alignment_summary_phrase(
        self,
        *,
        requirement: str,
        evidence: str,
    ) -> str:
        text = re.sub(r"\s+", " ", str(evidence or "")).strip(" .;-–—•")
        if not text:
            return self._display_relevance_label(requirement)

        leading_action_pattern = r"^(Сократил|Сократила|Снизил|Снизила|Ускорил|Ускорила|Улучшил|Улучшила|Внедрил|Внедрила|Создал|Создала|Разработал|Разработала|Участвовал|Участвовала|Провёл|Провел|Провела|Перевёл|Перевел|Перевела|Настроил|Настроила|Оптимизировал|Оптимизировала|Автоматизировал|Автоматизировала|Мигрировал|Мигрировала|Рефакторил|Модернизировал)\s+"
        stripped = re.sub(leading_action_pattern, "", text, flags=re.IGNORECASE)
        stripped = re.sub(r"^(по|для|на)\s+", "", stripped, flags=re.IGNORECASE)
        polished = humanize_experience_phrase(stripped or self._display_relevance_label(requirement))
        return polished or self._display_relevance_label(requirement)

    def _dedupe_top_alignment_evidence(
        self,
        values: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in values:
            requirement = str(item.get("requirement") or "").strip()
            summary_phrase = str(item.get("summary_phrase") or "").strip()
            signature = (requirement.casefold(), summary_phrase.casefold())
            if not requirement or not summary_phrase or signature in seen:
                continue
            seen.add(signature)
            result.append(item)
        return result

    def _requirement_supported_by_skills(
        self,
        *,
        requirement: str,
        selected_skill_keys: set[str],
    ) -> bool:
        requirement_key = self._normalize_display_skill(requirement).strip().lower()
        if requirement_key in selected_skill_keys:
            return True

        selected_text = " ".join(selected_skill_keys)
        requirement_lower = requirement_key

        support_markers = {
            "pytest": ("pytest", "test", "testing", "testclient"),
            "api": ("fastapi", "backend", "api"),
            "fastapi": ("fastapi", "backend", "api"),
            "backend": ("fastapi", "backend", "api"),
            "docker": ("docker", "container", "infrastructure"),
            "cicd": ("ci", "cd", "cicd", "pipeline"),
            "ci/cd": ("ci", "cd", "cicd", "pipeline"),
            "postgresql": ("postgres", "postgresql", "sqlalchemy"),
            "sqlalchemy": ("postgres", "postgresql", "sqlalchemy"),
            "workflow automation": ("workflow", "automation", "nocode", "no-code"),
            "git": ("git", "github", "repository", "version control"),
            "python": ("python",),
        }

        for marker, support_tokens in support_markers.items():
            if marker in requirement_lower and any(token in selected_text for token in support_tokens):
                return True

        return False

    def _calculate_total_experience_years(self, experience_items: list[dict[str, Any]]) -> int:
        """
        PR-38: Считает общий стаж работы в годах на основе experience_items.
        Возвращает целое число лет.
        """
        from datetime import date

        total_days = 0
        today = date.today()

        for item in experience_items:
            start = item.get("start_date")
            end = item.get("end_date")
            if not start and item.get("period"):
                start, end = self._parse_experience_period_dates(str(item.get("period") or ""))

            # Пропускаем если нет даты начала
            if not start:
                continue

            # Если нет даты окончания — считаем до сегодняшнего дня
            if not end:
                end = today

            # Считаем разницу в днях
            delta = end - start
            if delta.days > 0:
                total_days += delta.days

        # Конвертируем дни в годы (приблизительно 365.25 дней в году)
        return int(total_days / 365.25)

    def _parse_experience_period_dates(self, period: str):
        from datetime import date

        cleaned = re.sub(r"\s+", " ", str(period or "")).strip()
        match = re.match(
            r"^(?P<start_month>\d{2})\.(?P<start_year>\d{4})\s*-\s*(?P<end>н\.в\.|(?P<end_month>\d{2})\.(?P<end_year>\d{4}))$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            return None, None

        start = date(int(match.group("start_year")), int(match.group("start_month")), 1)
        if match.group("end").casefold() == "н.в.":
            return start, None
        return start, date(int(match.group("end_year")), int(match.group("end_month")), 1)

    def _split_resume_focus_source(self, value: str) -> list[str]:
        return self.narrative_builder.split_resume_focus_source(
            value,
            responsibility_boundaries=EXPERIENCE_RESPONSIBILITY_BOUNDARIES,
        )

    def _build_resume_achievement_sentence(
        self,
        selected_achievements: list[dict[str, Any]],
        *,
        role: str = "",
    ) -> str | None:
        return self.achievement_verbalizer.build_resume_achievement_action_sentence(
            selected_achievements,
            role=role,
        )

    def _render_alignment_evidence_label(
        self,
        evidence: dict[str, Any],
    ) -> str | None:
        for field in ("title", "snippet_text"):
            value = re.sub(r"\s+", " ", str(evidence.get(field) or "")).strip()
            display_value = make_user_facing_evidence_phrase(value)
            if display_value and display_value.lower() != "technology stack from resume":
                return (
                    display_value[:140].rsplit(" ", 1)[0]
                    if len(display_value) > 140
                    else display_value
                )
        skills = [
            self._normalize_display_skill(str(skill))
            for skill in evidence.get("skills") or []
            if str(skill).strip()
        ]
        return ", ".join(self._dedupe_preserve_order(skills)[:3]) or None

    def _dedupe_vacancy_evidence_alignment(
        self,
        alignment: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in alignment:
            requirement = str(item.get("requirement") or "").strip()
            evidence = str(item.get("evidence") or "").strip()
            signature = (requirement.casefold(), evidence.casefold())
            if not requirement or signature in seen:
                continue
            seen.add(signature)
            result.append(item)
        return result

    def _build_vacancy_aligned_summary(
        self,
        *,
        vacancy_title: str,
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
        experience_items: list[dict[str, Any]],
        vacancy_evidence_alignment: list[dict[str, Any]] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
    ) -> str:
        role = humanize_resume_role(vacancy_title)

        focus_phrases = [
            str(item.get("summary_phrase") or "").strip()
            for item in (top_alignment_evidence or [])
            if str(item.get("summary_phrase") or "").strip()
            and not self._looks_like_achievement_focus_phrase(
                str(item.get("summary_phrase") or "")
            )
        ]

        if not focus_phrases:
            responsibility_items: list[str] = []
            for item in experience_items[:2]:
                responsibilities = item.get("responsibilities") or []
                if isinstance(responsibilities, list):
                    responsibility_items.extend(
                        str(value).strip()
                        for value in responsibilities
                        if str(value).strip()
                    )

                description_raw = str(item.get("description_raw") or "").strip()
                if description_raw and not responsibility_items:
                    responsibility_items.extend(
                        self._split_resume_focus_source(description_raw)
                    )

            focus_phrases = self._dedupe_preserve_order(responsibility_items)

        if not focus_phrases:
            focus_phrases = self.semantic_summary_ranker.rank_skills(
                skills=selected_skills,
                vacancy_title=vacancy_title,
                selected_achievements=selected_achievements,
                top_alignment_evidence=top_alignment_evidence or [],
            )[:3]

        focus_phrases = self._rank_resume_focus_phrases(
            focus_phrases=focus_phrases,
            vacancy_title=vacancy_title,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            top_alignment_evidence=top_alignment_evidence or [],
        )
        focus_phrases = self.narrative_builder.specialize_resume_summary_focus_phrases(
            role=role,
            focus_phrases=focus_phrases,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
        )
        summary_role = self.narrative_builder.specialize_resume_summary_role(
            role=role,
            focus_phrases=focus_phrases,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
        )
        is_supply_management_context = self.narrative_builder.is_resume_supply_management_context(
            role=summary_role,
            focus_phrases=focus_phrases,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
        )
        focus_limit = 4 if is_supply_management_context else 3
        focus = self._render_resume_summary_focus(focus_phrases[:focus_limit])

        # PR-38: Универсальный шаблон summary на основе стажа
        total_years = self._calculate_total_experience_years(experience_items)
        if is_supply_management_context:
            return self._build_supply_management_summary(
                total_years=total_years,
                focus_phrases=focus_phrases[:focus_limit],
                selected_achievements=selected_achievements,
            )

        if total_years >= 1:
            years_text = f"{total_years} лет"
            if total_years % 10 == 1 and total_years % 100 != 11:
                years_text = f"{total_years} год"
            elif total_years % 10 in [2, 3, 4] and total_years % 100 not in [12, 13, 14]:
                years_text = f"{total_years} года"
            summary_start = f"{summary_role} с опытом более {years_text} в {focus}."
        else:
            summary_start = f"{summary_role} с опытом в {focus}."

        second_sentence = self._build_resume_summary_second_sentence(
            focus_phrases=focus_phrases[:focus_limit],
            selected_achievements=selected_achievements,
            context=" ".join([summary_role, vacancy_title, *selected_skills]),
            vacancy_title=vacancy_title,
            selected_skills=selected_skills,
            top_alignment_evidence=top_alignment_evidence or [],
        )
        if second_sentence:
            summary_start += f" {second_sentence}"
        return summary_start

    def _rank_resume_focus_phrases(
        self,
        *,
        focus_phrases: list[str],
        vacancy_title: str,
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
        top_alignment_evidence: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        return self.semantic_summary_ranker.rank_focus_phrases(
            phrases=focus_phrases,
            vacancy_title=vacancy_title,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            top_alignment_evidence=top_alignment_evidence or [],
            source="top_alignment_evidence" if top_alignment_evidence else "responsibility",
        )

    def _resume_focus_phrase_score(self, phrase: str, context: str) -> int:
        return self.semantic_summary_ranker.score_phrase(
            phrase,
            context=context,
        )

    def _build_resume_summary_second_sentence(
        self,
        *,
        focus_phrases: list[str],
        selected_achievements: list[dict[str, Any]],
        context: str = "",
        vacancy_title: str = "",
        selected_skills: list[str] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
    ) -> str | None:
        strong_achievements = self._strong_summary_achievements(
            selected_achievements,
            vacancy_title=vacancy_title,
            selected_skills=selected_skills or [],
            top_alignment_evidence=top_alignment_evidence or [],
        )
        achievement_sentence = self._build_resume_achievement_sentence(
            strong_achievements,
        )
        if achievement_sentence:
            return achievement_sentence

        weak_achievement_count = max(len(selected_achievements) - len(strong_achievements), 0)
        specialization = self._build_resume_specialization_sentence(
            focus_phrases,
            context=context,
            has_weak_achievements=weak_achievement_count > 0,
        )
        if specialization:
            return specialization
        return None

    def _strong_summary_achievements(
        self,
        selected_achievements: list[dict[str, Any]],
        *,
        vacancy_title: str = "",
        selected_skills: list[str] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        return self.semantic_summary_ranker.strong_summary_achievements(
            selected_achievements,
            min_score=3,
            vacancy_title=vacancy_title,
            selected_skills=selected_skills or [],
            top_alignment_evidence=top_alignment_evidence or [],
        )

    def _achievement_summary_quality_score(self, achievement: dict[str, Any]) -> int:
        return self.semantic_summary_ranker.achievement_quality_score(achievement)

    def _looks_like_action_achievement(self, value: str) -> bool:
        return self.semantic_summary_ranker.looks_like_action_achievement(value)

    def _build_resume_specialization_sentence(
        self,
        focus_phrases: list[str],
        *,
        context: str = "",
        has_weak_achievements: bool = False,
    ) -> str | None:
        joined = " ".join([str(context or ""), *[str(value or "") for value in focus_phrases]]).casefold()
        has_specialization_context = bool(
            re.search(r"проект|project|workflow|automation|автоматизац|координац|команд|срок|бюджет", joined)
        )
        if not has_weak_achievements and not has_specialization_context:
            return None

        focus = self._render_resume_specialization_focus(focus_phrases[:3])
        if not focus:
            return None
        return f"Основная специализация — {focus}."

    def _render_resume_specialization_focus(self, focus_phrases: list[str]) -> str:
        phrases = [
            self._resume_specialization_focus_phrase(value)
            for value in focus_phrases
            if str(value or "").strip()
        ]
        phrases = self._dedupe_preserve_order([item for item in phrases if item])

        if not phrases:
            return ""
        if len(phrases) == 1:
            return phrases[0]
        if len(phrases) == 2:
            return f"{phrases[0]} и {phrases[1]}"
        return f"{', '.join(phrases[:-1])} и {phrases[-1]}"

    def _resume_specialization_focus_phrase(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        if not text:
            return ""

        lowered = text.casefold()
        if lowered.startswith("планирование сроков и бюджета"):
            text = "контроль сроков и бюджета"
        else:
            text = text[:1].lower() + text[1:]

        if re.search(r"\b(?:it|ит)[-\s]?проект", text, flags=re.IGNORECASE):
            text = re.sub(r"\bIT-проектами\b", "ИТ-проектами", text, flags=re.IGNORECASE)
            text = re.sub(r"\bит-проектами\b", "ИТ-проектами", text, flags=re.IGNORECASE)
            if "полного цикла" not in text.casefold():
                text = re.sub(
                    r"\bИТ-проектами\b",
                    "ИТ-проектами полного цикла",
                    text,
                    flags=re.IGNORECASE,
                )

        text = re.sub(
            r"\bкоманды\s+(\d+)\s+человек\b",
            r"команды до \1 человек",
            text,
            flags=re.IGNORECASE,
        )
        return text

    def _looks_like_achievement_focus_phrase(self, value: str) -> bool:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        lowered = text.casefold()
        if "%" in text or re.search(r"\b\d+\b", text):
            return True
        return lowered.startswith(
            (
                "сокращение ",
                "снижение ",
                "увеличение ",
                "оптимизация ",
                "ускорение ",
            )
        )

    def _render_resume_summary_focus(self, focus_phrases: list[str]) -> str:
        phrases = [
            self._resume_summary_focus_phrase(value)
            for value in focus_phrases
            if str(value or "").strip()
        ]
        phrases = self._dedupe_preserve_order([item for item in phrases if item])

        if not phrases:
            return "релевантных профессиональных задач"
        if len(phrases) == 1:
            return phrases[0]
        if len(phrases) == 2:
            return f"{phrases[0]} и {phrases[1]}"
        return f"{', '.join(phrases[:-1])} и {phrases[-1]}"

    def _resume_summary_focus_phrase(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        if not text:
            return ""

        replacements = {
            "управление ": "управлении ",
            "координация ": "координации ",
            "планирование сроков и бюджета": "контроле сроков и бюджета",
            "планирование ": "планировании ",
            "ведение ": "ведении ",
            "взаимодействие ": "взаимодействии ",
            "организация ": "организации ",
            "контроль ": "контроле ",
            "разработка ": "разработке ",
            "настройка ": "настройке ",
            "интеграция ": "интеграции ",
            "подготовка ": "подготовке ",
            "сопровождение ": "сопровождении ",
            "анализ ": "анализе ",
            "обслуживание ": "сфере обслуживания ",
            "ремонт ": "ремонта ",
            "устранение ": "устранения ",
        }

        lowered = text.casefold()
        for source, target in replacements.items():
            if lowered.startswith(source):
                text = target + text[len(source):]
                break

        if re.search(r"\b(?:it|ит)[-\s]?проект", text, flags=re.IGNORECASE):
            text = re.sub(r"\bIT-проектами\b", "ИТ-проектами", text, flags=re.IGNORECASE)
            text = re.sub(r"\bит-проектами\b", "ИТ-проектами", text, flags=re.IGNORECASE)
            if "полного цикла" not in text.casefold():
                text = re.sub(
                    r"\bИТ-проектами\b",
                    "ИТ-проектами полного цикла",
                    text,
                    flags=re.IGNORECASE,
                )

        text = re.sub(
            r"\bкоманды\s+(\d+)\s+человек\b",
            r"команды до \1 человек",
            text,
            flags=re.IGNORECASE,
        )

        return text[:1].lower() + text[1:]

    def _build_supply_management_summary(
        self,
        *,
        total_years: int,
        focus_phrases: list[str],
        selected_achievements: list[dict[str, Any]],
    ) -> str:
        if total_years >= 1:
            years_text = f"{total_years} лет"
            if total_years % 10 == 1 and total_years % 100 != 11:
                years_text = f"{total_years} год"
            elif total_years % 10 in [2, 3, 4] and total_years % 100 not in [12, 13, 14]:
                years_text = f"{total_years} года"
            first_sentence = (
                f"Более {years_text} работаю в сфере "
                "материально-технического обеспечения и закупок."
            )
        else:
            first_sentence = (
                "Работаю в сфере материально-технического обеспечения и закупок."
            )

        focus = self._build_supply_management_focus_value(focus_phrases)
        sentences = [
            first_sentence,
            f"Основной опыт связан с {focus}.",
        ]

        achievement_value = self._build_supply_management_achievement_value(
            selected_achievements,
        )
        if achievement_value:
            sentences.append(f"За время работы реализовал проекты по {achievement_value}.")

        return " ".join(sentences)

    def _build_supply_management_focus_value(self, focus_phrases: list[str]) -> str:
        corpus = " ".join(str(value or "").casefold() for value in focus_phrases)
        values: list[str] = []
        if re.search(r"закуп|(?<!водо)снабжен|\bмто\b", corpus):
            values.append("организацией снабжения")
        if "поставщик" in corpus:
            values.append("управлением поставщиками")
        if any(marker in corpus for marker in ("бюджет", "затрат")):
            values.append("бюджетированием")
        if any(marker in corpus for marker in ("логист", "поставк", "склад")):
            values.append("контролем логистических процессов")

        if not values:
            return format_summary_focus_phrases(focus_phrases)
        return format_summary_focus_phrases(values[:4])

    def _build_supply_management_achievement_value(
        self,
        selected_achievements: list[dict[str, Any]],
    ) -> str:
        phrases = [
            self._to_project_po_case(
                self.achievement_verbalizer.nounize_achievement_phrase(
                    str(item.get("title") or "")
                )
            )
            for item in selected_achievements[:3]
            if str(item.get("title") or "").strip()
        ]
        phrases = self._dedupe_preserve_order([phrase for phrase in phrases if phrase])
        if not phrases:
            return ""
        if len(phrases) == 1:
            return phrases[0]
        if len(phrases) == 2:
            return " и ".join(phrases)
        return f"{', '.join(phrases[:-1])} и {phrases[-1]}"

    def _to_project_po_case(self, value: str) -> str:
        replacements = {
            "автоматизация": "автоматизации",
            "ведение": "ведению",
            "внедрение": "внедрению",
            "координация": "координации",
            "настройка": "настройке",
            "оптимизация": "оптимизации",
            "организация": "организации",
            "подготовка": "подготовке",
            "построение": "построению",
            "проведение": "проведению",
            "разработка": "разработке",
            "реализация": "реализации",
            "снижение": "снижению",
            "сокращение": "сокращению",
            "создание": "созданию",
            "сопровождение": "сопровождению",
            "увеличение": "увеличению",
            "улучшение": "улучшению",
            "управление": "управлению",
        }
        text = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        if not text:
            return ""
        first, _, rest = text.partition(" ")
        replacement = replacements.get(first.casefold())
        if not replacement:
            return text
        return f"{replacement} {rest}".strip()

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
        best: tuple[float, dict[str, Any]] | None = None
        fallback_best: tuple[float, dict[str, Any]] | None = None

        for snippet in evidence_snippets:
            candidate_terms = [
                str(snippet.get("title") or ""),
                str(snippet.get("snippet_text") or ""),
                *[str(skill) for skill in snippet.get("skills") or []],
            ]
            text = " ".join(candidate_terms).lower()

            score = float(sum(1 for token in competency_tokens if token in text))
            marker_score = sum(
                1 for marker in competency_markers if marker in text
            )

            semantic_result = self.semantic_matcher.match(
                competency,
                candidate_terms,
            )
            semantic_score = 0.0
            if semantic_result.matched:
                semantic_score = semantic_result.confidence * 5.0

            if competency_markers and marker_score <= 0 and not semantic_score:
                if requires_direct_evidence:
                    continue
                if score > 0 and (
                    fallback_best is None or score > fallback_best[0]
                ):
                    fallback_best = (score, snippet)
                continue

            score += marker_score * 4
            score += semantic_score
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
        raw_experiences = list(getattr(profile, "experiences", []) or [])

        for exp in raw_experiences[:5]:
            item = {
                "company": exp.company,
                "role": exp.role,
                "period": self._format_period(exp.start_date, exp.end_date),
                "description_raw": self._humanize_supply_experience_description(
                    self._normalize_experience_description(exp.description_raw)
                ),
            }

            if self._looks_like_low_confidence_experience_item(item):
                continue

            items.append(item)

        if items or not raw_experiences:
            return items

        fallback_items: list[dict] = []
        for exp in raw_experiences[:5]:
            fallback_items.append(
                {
                    "company": exp.company,
                    "role": exp.role,
                    "period": self._format_period(exp.start_date, exp.end_date),
                    "description_raw": self._humanize_supply_experience_description(
                        self._normalize_experience_description(exp.description_raw)
                    ),
                }
            )

        return fallback_items

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

    def _humanize_supply_experience_description(self, value: str | None) -> str | None:
        if not value:
            return value

        lines = [
            re.sub(r"\s+", " ", line).strip(" .;-–—•")
            for line in str(value).splitlines()
            if line.strip(" .;-–—•")
        ]
        if len(lines) < 3:
            return value

        corpus = " ".join(lines).casefold()
        if not re.search(r"закуп|(?<!водо)снабжен|поставщик|склад", corpus):
            return value

        sentences: list[str] = []
        if re.search(r"закуп|(?<!водо)снабжен|поставщик", corpus):
            if "поставщик" in corpus:
                sentences.append(
                    "Отвечал за организацию закупочной деятельности и управление поставщиками."
                )
            else:
                sentences.append("Отвечал за организацию закупочной деятельности.")

        if any(marker in corpus for marker in ("бюджет", "логист", "постав", "склад")):
            objects: list[str] = []
            if "бюджет" in corpus:
                objects.append("бюджет снабжения")
            if "склад" in corpus:
                objects.append("складские запасы")
            if any(marker in corpus for marker in ("логист", "постав")):
                objects.append("логистические процессы")
            if objects:
                sentences.append(f"Контролировал {format_summary_focus_phrases(objects)}.")

        if any(marker in corpus for marker in ("отдел", "договор", "обязательств")):
            sentences.append(
                "Руководил работой отдела снабжения и обеспечивал исполнение договорных обязательств."
            )

        return "\n".join(self._dedupe_preserve_order(sentences)) if sentences else value

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
                        "Оценка соответствия вакансии сейчас низкая, потому что "
                        "структурированное покрытие профиля пока ограничено"
                    ),
                    severity="warning",
                )
            )

        if missing_keywords:
            warnings.append(
                build_warning(
                    code="missing_vacancy_keywords",
                    message=(
                        "Ключевые слова вакансии представлены слабо или отсутствуют: "
                        f"{', '.join(missing_keywords[:6])}"
                    ),
                    severity="warning",
                )
            )

        warnings.append(
            build_warning(
                code="ats_plaintext_draft",
                message=(
                    "Черновик резюме подготовлен в ATS-совместимом текстовом виде "
                    "и пока не является финально оформленной версией"
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

        # Factuality-gate: отсекаем выдуманные AI-метрики, отсутствующие в оригинале
        # (baseline — метрики исходного ATS-текста; если AI ввёл новую метрику,
        # возвращаем оригинал, следуя принципу «ИИ не добавляет факты»).
        original_metrics = _extract_metrics(resume_text)
        if original_metrics and (_extract_metrics(enhanced) - original_metrics):
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
