# app\services\profile_structuring_service.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from calendar import monthrange
from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateExperience, CandidateProfile
from app.domain.evidence import build_evidence_fingerprint, extract_skill_tags
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.services.core_service_policy import LEGACY_CANDIDATE_SPECIFIC_HEURISTIC
from app.services.evidence_strength_service import EvidenceStrengthService
from app.services.legacy_resume_recovery_service import LegacyResumeRecoveryService


DATE_RANGE_RE = re.compile(
    r"^\d{2}\.\d{4}\s*[—–-]\s*(?:\d{2}\.\d{4}|настоящее время|н\.в\.)$",
    re.IGNORECASE,
)
INLINE_DATE_RANGE_RE = re.compile(
    r"(?P<start>\d{2}\.\d{2}\.\d{4}|\d{2}\.\d{4}|\d{4})\s*[—–-]\s*(?P<end>\d{2}\.\d{2}\.\d{4}|\d{2}\.\d{4}|\d{4}|по настоящее время|настоящее время|н\.в\.)",
    re.IGNORECASE,
)
MONTH_YEAR_DATE_RANGE_RE = re.compile(
    r"^(?P<start>\d{2}\.\d{4})\s*[—–-]\s*(?P<end>\d{2}\.\d{4}|настоящее время|н\.в\.)$",
    re.IGNORECASE,
)
NUMBERED_ITEM_RE = re.compile(r"^\d{1,2}\s*[.)\-–—:]\s+")
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")


STRUCTURED_V2_SECTION_HEADINGS = {
    "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ",
    "НАВЫКИ",
    "ЦЕЛЕВАЯ ДОЛЖНОСТЬ",
    "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
    "ГОРОД",
    "ОПЫТ РАБОТЫ",
    "ОПЫТ",
    "ОБРАЗОВАНИЕ",
    "ПРОЕКТЫ",
    "ПОРТФОЛИО",
    "СТАЖИРОВКИ",
    "КУРСЫ",
    "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ",
    "КОНТАКТЫ",
    "О СЕБЕ",
}


@dataclass
class StructuredExperienceDraft:
    company: str
    role: str
    start_date: date | None
    end_date: date | None
    description_raw: str | None
    order_index: int


@dataclass
class StructuredContactDraft:
    email: str | None = None
    phone: str | None = None
    github: str | None = None
    telegram: str | None = None
    address: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "email": self.email,
            "phone": self.phone,
            "github": self.github,
            "telegram": self.telegram,
            "address": self.address,
        }


@dataclass
class StructuredResumeSignal:
    title: str
    category: str
    skills: list[str] = field(default_factory=list)
    snippet_text: str | None = None
    fact_status: str = "user_provided"
    source_type: str = "resume_structured"
    source_layer: str = "generic_extraction"
    ownership_confidence: str = "medium"
    requires_confirmation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "category": self.category,
            "skills": list(self.skills),
            "snippet_text": self.snippet_text or self.title,
            "fact_status": self.fact_status,
            "source_type": self.source_type,
            "source_layer": self.source_layer,
            "ownership_confidence": self.ownership_confidence,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass
class StructuredEducationDraft:
    institution: str
    degree: str | None = None
    specialty: str | None = None
    period: str | None = None
    details: str | None = None


@dataclass
class StructuredProfileDraft:
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    contacts: StructuredContactDraft = field(default_factory=StructuredContactDraft)
    summary: str | None = None
    target_roles: list[str] = field(default_factory=list)
    experiences: list[StructuredExperienceDraft] = field(default_factory=list)
    education: list[StructuredEducationDraft] = field(default_factory=list)
    courses: list[StructuredResumeSignal] = field(default_factory=list)
    projects: list[StructuredResumeSignal] = field(default_factory=list)
    portfolio_projects: list[StructuredResumeSignal] = field(default_factory=list)
    internships: list[StructuredResumeSignal] = field(default_factory=list)
    achievements: list[StructuredResumeSignal] = field(default_factory=list)
    ai_tools: list[str] = field(default_factory=list)
    automation_tools: list[str] = field(default_factory=list)
    workflow_experience: list[StructuredResumeSignal] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    evidence_snippets: list[StructuredResumeSignal] = field(default_factory=list)
    competency_signals: list[StructuredResumeSignal] = field(default_factory=list)
    contribution_signals: list[StructuredResumeSignal] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ProfileStructuringService:
    legacy_private_recovery_marker = LEGACY_CANDIDATE_SPECIFIC_HEURISTIC

    def __init__(
        self,
        file_extraction_repository: FileExtractionRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        evidence_snippet_repository: EvidenceSnippetRepository | None = None,
        evidence_strength_service: EvidenceStrengthService | None = None,
        enable_legacy_recovery: bool = True,
    ) -> None:
        self.file_extraction_repository = file_extraction_repository or FileExtractionRepository()
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.evidence_snippet_repository = (
            evidence_snippet_repository or EvidenceSnippetRepository()
        )
        self.evidence_strength_service = evidence_strength_service or EvidenceStrengthService()
        self.legacy_recovery_service = LegacyResumeRecoveryService(
            enabled=enable_legacy_recovery,
        )

    async def extract_into_profile(
        self,
        session: AsyncSession,
        *,
        extraction_id: UUID,
        user_id: UUID,
    ) -> tuple[CandidateProfile, StructuredProfileDraft]:
        extraction = await self.file_extraction_repository.get_by_id(
            session,
            extraction_id,
            user_id=user_id,
        )
        if extraction is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="file extraction not found",
            )

        source_file_kind = "resume"
        if extraction.source_file is not None:
            source_file_kind = str(extraction.source_file.file_kind or "").strip().lower()

        draft = self._build_draft(
            extraction.extracted_text,
            source_file_kind=source_file_kind,
        )

        profile = await self.candidate_profile_repository.get_by_user_id(
            session,
            user_id,
        )
        if profile is None:
            profile = await self.candidate_profile_repository.create_empty(
                session,
                user_id=user_id,
        )

        if source_file_kind not in {"portfolio", "other"}:
            self._apply_profile_fields(profile, draft)
            await self._replace_experiences(session, profile.id, draft.experiences)
        await self._upsert_structured_evidence(session, user_id=user_id, draft=draft)

        await session.flush()
        await session.refresh(profile)
        return profile, draft

    def _looks_like_generated_application_document(self, text: str) -> bool:
        normalized = str(text or "").upper()
        strong_markers = (
            "РЕЛЕВАНТНО ДЛЯ ВАКАНСИИ",
            "КАРТА КОМПЕТЕНЦИЙ",
            "ПИСЬМО:",
            "ЗДРАВСТВУЙТЕ!",
        )
        if any(marker in normalized for marker in strong_markers):
            return True

        return (
            "ЦЕЛЕВАЯ ПОЗИЦИЯ" in normalized
            and "КРАТКОЕ РЕЗЮМЕ" in normalized
            and "ОПЫТ РАБОТЫ" not in normalized
        )

    def _build_draft(
        self,
        text: str,
        *,
        source_file_kind: str | None = None,
    ) -> StructuredProfileDraft:
        draft = StructuredProfileDraft()

        if self._looks_like_generated_application_document(text):
            draft.warnings.append(
                "uploaded document looks like a generated application package, not a source resume"
            )
            return draft

        lines = self._split_inline_resume_headings(self._clean_lines(text))
        compact_name, compact_headline = self._extract_name_and_headline_from_compact_first_line(lines)

        draft.full_name = self._extract_full_name(lines)
        if not draft.full_name and compact_name:
            draft.full_name = compact_name
        elif compact_name and (
            not draft.full_name
            or (compact_headline and compact_headline.lower() in draft.full_name.lower())
        ):
            draft.full_name = compact_name
        if not draft.full_name or self._normalize_heading(draft.full_name) in {
            "ЦЕЛЕВАЯ ДОЛЖНОСТЬ",
            "ГОРОД",
            "ОПЫТ РАБОТЫ",
            "НАВЫКИ",
        }:
            draft.full_name = self._extract_full_name_from_top_lines(lines)

        draft.location = self._extract_location(lines)
        draft.contacts = self._extract_contacts(lines)
        draft.summary = self._extract_skills_summary(lines)
        draft.target_roles = self._extract_target_roles(lines)
        if not draft.target_roles:
            inferred_role = self._infer_headline_role_from_top_lines(lines, draft.full_name)
            if inferred_role:
                draft.target_roles = [inferred_role]
        if not draft.target_roles and compact_headline:
            draft.target_roles = [compact_headline]
        draft.headline = ", ".join(draft.target_roles[:3]) if draft.target_roles else None
        draft.experiences = self._extract_experiences(lines)
        draft.education = self._extract_education(lines)
        draft.courses = self._extract_courses(lines)
        self._apply_structured_resume_v2(
            lines,
            draft,
            source_file_kind=source_file_kind,
        )

        if compact_name and compact_headline and draft.full_name:
            if compact_headline.lower() in draft.full_name.lower():
                draft.full_name = compact_name

        if not draft.full_name:
            draft.warnings.append("full_name was not extracted confidently")
        if not draft.target_roles:
            draft.warnings.append("target roles were not extracted")
        if not draft.experiences:
            draft.warnings.append("work experience section was not parsed")

        if not draft.evidence_snippets:
            draft.warnings.append("structured resume v2 did not find reusable evidence snippets")
        if not draft.technologies:
            draft.warnings.append("structured resume v2 did not find technologies confidently")

        return draft

    async def _upsert_structured_evidence(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        draft: StructuredProfileDraft,
    ) -> None:
        payloads: list[dict[str, Any]] = []

        for signal in draft.evidence_snippets:
            snippet_text = signal.snippet_text or signal.title
            skills = self._dedupe_preserve_order(signal.skills)
            source_type = str(signal.source_type or "resume_structured").strip().lower()
            strength = self.evidence_strength_service.classify_strength(
                self.evidence_strength_service.calculate_strength_score(
                    {
                        "title": signal.title,
                        "snippet_text": snippet_text,
                        "fact_status": signal.fact_status,
                        "skills": skills,
                    }
                )
            )
            payloads.append(
                {
                    "fingerprint": build_evidence_fingerprint(
                        user_id=str(user_id),
                        title=signal.title,
                        snippet_text=snippet_text,
                        source_type=source_type,
                        skills=skills,
                        fact_status=signal.fact_status,
                    ),
                    "title": signal.title,
                    "snippet_text": snippet_text,
                    "source_type": source_type,
                    "skills": skills,
                    "evidence_strength": str(strength),
                    "fact_status": signal.fact_status,
                    "usage_count": 0,
                    "used_in_documents_count": 0,
                    "used_in_interviews_count": 0,
                    "star_summary": {
                        "category": signal.category,
                        "source": (
                            "portfolio_project_extraction_v1"
                            if signal.category == "portfolio_project"
                            else "structured_resume_extraction_v2"
                        ),
                        "fact_status": signal.fact_status,
                    },
                }
            )

        if payloads:
            await self.evidence_snippet_repository.upsert_many(
                session,
                user_id=user_id,
                snippets=payloads,
            )

    def _apply_profile_fields(
        self,
        profile: CandidateProfile,
        draft: StructuredProfileDraft,
    ) -> None:
        if draft.full_name:
            profile.full_name = draft.full_name
        if draft.headline:
            profile.headline = draft.headline
        if draft.location:
            profile.location = draft.location
        if draft.summary:
            profile.summary = draft.summary
        if draft.target_roles:
            profile.target_roles_json = draft.target_roles
        if draft.technologies:
            profile.technologies_json = draft.technologies
        # Этап 7: автодетект рынка из location только если profile.market ещё
        # не задан явно (user-override и intake-значение не перетираются).
        if not profile.market and draft.location:
            inferred = self._infer_market_from_location(draft.location)
            if inferred:
                profile.market = inferred

    async def _replace_experiences(
        self,
        session: AsyncSession,
        profile_id: UUID,
        experiences: list[StructuredExperienceDraft],
    ) -> None:
        await session.execute(
            delete(CandidateExperience).where(CandidateExperience.profile_id == profile_id)
        )

        for item in experiences:
            session.add(
                CandidateExperience(
                    profile_id=profile_id,
                    company=item.company,
                    role=item.role,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    description_raw=item.description_raw,
                    order_index=item.order_index,
                )
            )

        await session.flush()

    def _clean_lines(self, text: str) -> list[str]:
        cleaned_lines: list[str] = []
        for raw_line in text.splitlines():
            line = ZERO_WIDTH_RE.sub("", raw_line).strip()
            if line:
                cleaned_lines.append(line)
        return cleaned_lines

    def _apply_structured_resume_v2(
        self,
        lines: list[str],
        draft: StructuredProfileDraft,
        *,
        source_file_kind: str | None = None,
    ) -> None:
        text = "\n".join(lines)
        project_signals = [
            *self._extract_project_like_signals(lines),
            *self._extract_achievement_signals(lines),
        ]
        internship_signals = self._extract_internship_signals(lines)
        portfolio_project_signals = self._extract_portfolio_project_signals(
            lines,
            source_file_kind=source_file_kind,
        )
        internship_title_keys = {
            signal.title.casefold()
            for signal in internship_signals
        }
        project_signals_without_internships = [
            signal
            for signal in project_signals
            if signal.title.casefold() not in internship_title_keys
        ]
        technology_signals = self._extract_technology_signals(text)

        skills_text = self._extract_skills_summary(lines) or ""
        explicit_skill_signals = self._extract_inline_skills_from_lines(skills_text.splitlines())

        technology_signals = self._dedupe_preserve_order(
            [
                *technology_signals,
                *explicit_skill_signals,
            ]
        )

        competency_signals = self._extract_competency_signals(lines, technology_signals)

        draft.projects = [
            signal
            for signal in project_signals_without_internships
            if signal.category in {"project", "ai_project", "automation", "prompt_engineering"}
        ]
        draft.portfolio_projects = portfolio_project_signals
        draft.internships = self._dedupe_signals(
            [
                *[
                    signal
                    for signal in project_signals_without_internships
                    if signal.category == "internship"
                ],
                *internship_signals,
            ]
        )
        draft.achievements = [
            signal
            for signal in project_signals
            if signal.category == "achievement"
        ]
        if not draft.achievements:
            # GENERAL fallback: явного раздела «Достижения»/«Ключевые
            # достижения» нет — относим реальные нумерованные
            # project/internship-блоки (стажировки, проекты) к достижениям.
            # Это НЕ выдумывание (decision-rules: «запрещается выдумывать
            # достижения») — контент целиком взят из текста резюме.
            # Люди без стажировок/проектов получают пустой список
            # (project_signals и internship_signals пусты) — корректно.
            achievement_fallback: list[StructuredResumeSignal] = []
            seen_titles: set[str] = set()
            for signal in (*project_signals_without_internships, *internship_signals):
                if signal.category not in {
                    "project",
                    "ai_project",
                    "automation",
                    "prompt_engineering",
                    "internship",
                }:
                    continue
                key = (signal.title or "").casefold()
                if not key or key in seen_titles:
                    continue
                seen_titles.add(key)
                achievement_fallback.append(
                    StructuredResumeSignal(
                        title=signal.title,
                        category="achievement",
                        skills=signal.skills,
                        snippet_text=signal.snippet_text,
                    )
                )
            draft.achievements = self._dedupe_signals(achievement_fallback)
        draft.workflow_experience = [
            signal
            for signal in project_signals_without_internships + competency_signals
            if signal.category in {"automation", "workflow_experience", "competency_signal"}
        ]
        draft.technologies = technology_signals
        draft.ai_tools = [
            item
            for item in technology_signals
            if item in {"AI", "LLM", "ChatGPT", "TensorFlow", "neural networks"}
        ]
        draft.automation_tools = [
            item
            for item in technology_signals
            if item in {"automation", "API", "workflow"}
        ]
        draft.competency_signals = competency_signals
        draft.contribution_signals = self._build_normalized_contribution_signals(
            [
                *project_signals_without_internships,
                *internship_signals,
                *portfolio_project_signals,
                *[
                    signal
                    for signal in project_signals
                    if signal.category == "achievement"
                ],
            ]
        )

        project_titles = {
            signal.title.casefold()
            for signal in project_signals
        }
        evidence_candidates = [
            *project_signals,
            *[
                signal
                for signal in internship_signals
                if signal.title.casefold() not in project_titles
            ],
            *portfolio_project_signals,
            *competency_signals,
        ]
        if technology_signals:
            evidence_candidates.append(
                StructuredResumeSignal(
                    title="Technology stack from resume",
                    category="technologies",
                    skills=technology_signals,
                    snippet_text=", ".join(technology_signals),
                )
            )

        draft.evidence_snippets = self._dedupe_signals(evidence_candidates)

    def _extract_portfolio_project_signals(
        self,
        lines: list[str],
        *,
        source_file_kind: str | None = None,
    ) -> list[StructuredResumeSignal]:
        if not self._should_extract_portfolio_projects(lines, source_file_kind):
            return []

        signals: list[StructuredResumeSignal] = []
        for block in self._split_portfolio_project_blocks(lines):
            title = self._clean_portfolio_project_title(block[0])
            if not title:
                continue

            snippet_text = self._clean_portfolio_project_snippet(block)
            if not snippet_text:
                continue

            signals.append(
                StructuredResumeSignal(
                    title=title,
                    category="portfolio_project",
                    skills=self._extract_signal_skills(title, snippet_text),
                    snippet_text=snippet_text,
                    source_type="resume_structured",
                )
            )

        return self._dedupe_signals(signals)

    def _should_extract_portfolio_projects(
        self,
        lines: list[str],
        source_file_kind: str | None,
    ) -> bool:
        normalized_kind = str(source_file_kind or "").strip().lower()
        if normalized_kind in {"portfolio", "other"}:
            return True

        normalized_text = "\n".join(self._normalize_heading(line) for line in lines[:20])
        return any(
            marker in normalized_text
            for marker in ("ПОРТФОЛИО", "PORTFOLIO", "ПЕТ-ПРОЕКТ", "PET PROJECT")
        )

    def _split_portfolio_project_blocks(self, lines: list[str]) -> list[list[str]]:
        content_lines = self._portfolio_content_lines(lines)
        blocks: list[list[str]] = []
        current: list[str] = []

        for line in content_lines:
            if self._looks_like_portfolio_project_title(line):
                if current:
                    blocks.append(current)
                current = [line]
                continue

            if current:
                current.append(line)

        if current:
            blocks.append(current)

        return [
            block[:8]
            for block in blocks
            if self._portfolio_project_block_has_evidence(block)
        ]

    def _portfolio_content_lines(self, lines: list[str]) -> list[str]:
        content: list[str] = []
        started = False
        for line in lines:
            normalized = self._normalize_heading(line)
            if normalized in {"ПОРТФОЛИО", "PORTFOLIO", "ПРОЕКТЫ", "PROJECTS"}:
                started = True
                continue
            if normalized.startswith(("ПОРТФОЛИО ", "PORTFOLIO ", "ПРОЕКТЫ ", "PROJECTS ")):
                started = True
                remainder = re.sub(
                    r"^(портфолио|portfolio|проекты|projects)\s*[:：-]?\s*",
                    "",
                    line.strip(),
                    flags=re.IGNORECASE,
                ).strip()
                if remainder:
                    content.append(remainder)
                continue
            if started or not self._looks_like_layout_heading(line):
                content.append(line)
        return content

    def _looks_like_portfolio_project_title(self, line: str) -> bool:
        cleaned = self._clean_portfolio_project_title(line)
        if not cleaned:
            return False

        lowered = cleaned.lower()
        if any(
            lowered.startswith(prefix)
            for prefix in (
                "стек",
                "технологии",
                "задача",
                "результат",
                "описание",
                "роль",
                "ссылка",
                "github",
                "demo",
            )
        ):
            return False

        if len(cleaned) > 110:
            return False
        if cleaned.endswith(".") and len(cleaned.split()) > 4:
            return False

        title_markers = (
            "проект",
            "bot",
            "бот",
            "shop",
            "app",
            "сервис",
            "система",
            "dashboard",
            "pipeline",
            "monitoring",
            "мониторинг",
            "анализ",
            "contract",
            "review",
            "playbook",
            "цветизац",
            "нейро",
            "ai",
            "ии",
        )
        if any(marker in lowered for marker in title_markers):
            return True

        return bool(
            re.match(r"^(?:\d{1,2}[.)\-–—:]\s+|[-•]\s+|#{1,4}\s+)", line.strip())
        )

    def _portfolio_project_block_has_evidence(self, block: list[str]) -> bool:
        if len(block) < 2:
            return False
        text = " ".join(block).lower()
        evidence_markers = (
            "python",
            "api",
            "sql",
            "telegram",
            "bot",
            "бот",
            "ai",
            "ии",
            "нейро",
            "computer vision",
            "машин",
            "данн",
            "автомат",
            "backend",
            "frontend",
            "стек",
            "результат",
            "разработ",
            "реализ",
            "интеграц",
            "prepared",
            "reduced",
            "legal",
            "contract",
        )
        return any(marker in text for marker in evidence_markers)

    def _clean_portfolio_project_title(self, line: str) -> str | None:
        title = re.sub(r"^\s*(?:\d{1,2}[.)\-–—:]|[-•]|#{1,4})\s*", "", line.strip())
        title = re.sub(r"^(?:проект|project)\s*[:：-]\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s+", " ", title).strip(" -–—•:;")
        if len(title) < 3:
            return None
        if self._looks_like_layout_heading(title):
            return None
        return title

    def _clean_portfolio_project_snippet(self, block: list[str]) -> str | None:
        snippet = re.sub(r"\s+", " ", " ".join(block)).strip()
        if len(snippet) > 360:
            snippet = snippet[:360].rsplit(" ", 1)[0].strip()
        return snippet or None

    def _extract_project_like_signals(self, lines: list[str]) -> list[StructuredResumeSignal]:
        section_start = self._find_project_or_internship_start(lines)
        if section_start is None:
            return []

        section_lines = lines[section_start + 1 :]
        blocks = self._split_numbered_signal_blocks(section_lines)
        if not blocks:
            section = self._extract_section(
                lines,
                start_heading=self._normalize_heading(lines[section_start]),
                stop_headings={"КУРСЫ", "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ", "О СЕБЕ", "КОНТАКТЫ"},
            )
            blocks = [[line] for line in section if not self._looks_like_layout_heading(line)]

        signals: list[StructuredResumeSignal] = []
        for block in blocks:
            title = self._clean_signal_title(block)
            if not title or self._looks_like_low_value_signal_title(title):
                continue

            raw_text = " ".join(block).strip()
            category = self._classify_signal_category(title, raw_text)
            skills = self._extract_signal_skills(title, raw_text)
            signals.append(
                StructuredResumeSignal(
                    title=title,
                    category=category,
                    skills=skills,
                    snippet_text=raw_text or title,
                )
            )

        return self._dedupe_signals(signals)

    def _extract_achievement_signals(self, lines: list[str]) -> list[StructuredResumeSignal]:
        signals: list[StructuredResumeSignal] = []
        capture = False

        for line in lines:
            normalized = self._normalize_heading(line)
            if normalized in {"ДОСТИЖЕНИЯ", "КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ"}:
                capture = True
                continue

            if not capture:
                continue

            if normalized in {
                "НАВЫКИ",
                "КЛЮЧЕВЫЕ НАВЫКИ",
                "ОБРАЗОВАНИЕ",
                "КУРСЫ",
                "ПРОЕКТЫ",
                "ОПЫТ РАБОТЫ",
                "ОПЫТ",
                "ОБЯЗАННОСТИ",
            }:
                capture = False
                continue

            cleaned = re.sub(r"\s+", " ", str(line or "")).strip(" .;-–—•")
            if not cleaned:
                continue

            if (
                signals
                and (
                    MONTH_YEAR_DATE_RANGE_RE.match(cleaned)
                    or DATE_RANGE_RE.search(cleaned)
                    or self._looks_like_company_line(cleaned)
                    or self._looks_like_role_line(cleaned)
                )
            ):
                capture = False
                continue

            for item in self._split_inline_achievement_items(cleaned):
                title = self._strip_company_suffix_from_achievement_text(item)
                if not title or not self._line_has_achievement_like_action(title):
                    continue
                signals.append(
                    StructuredResumeSignal(
                        title=title,
                        category="achievement",
                        skills=self._extract_signal_skills(title),
                        snippet_text=title,
                    )
                )

        return self._dedupe_signals(signals)

    def _extract_internship_signals(self, lines: list[str]) -> list[StructuredResumeSignal]:
        marker_index = self._find_internship_marker(lines)
        if marker_index is None:
            section = self._extract_section(
                lines,
                start_heading="СТАЖИРОВКИ",
                stop_headings={
                    "ОПЫТ РАБОТЫ",
                    "ОБРАЗОВАНИЕ",
                    "КУРСЫ",
                    "ПРОЕКТЫ",
                    "ПОРТФОЛИО",
                    "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ",
                    "КОНТАКТЫ",
                    "О СЕБЕ",
                },
            )
            blocks = self._split_numbered_signal_blocks(section)
            if not blocks and section:
                blocks = [[line] for line in section if not self._looks_like_layout_heading(line)]
        else:
            blocks = self._split_numbered_signal_blocks(lines[marker_index + 1 :])

        signals: list[StructuredResumeSignal] = []
        for block in blocks:
            cleaned_block = self._clean_internship_block(block)
            title = self._clean_signal_title(cleaned_block)
            if not title or self._looks_like_low_value_signal_title(title):
                continue

            raw_text = " ".join(cleaned_block).strip()
            signals.append(
                StructuredResumeSignal(
                    title=title,
                    category="internship",
                    skills=self._extract_signal_skills(title, raw_text),
                    snippet_text=raw_text or title,
                )
            )

        return self._dedupe_signals(signals)

    def _find_internship_marker(self, lines: list[str]) -> int | None:
        for idx, line in enumerate(lines):
            normalized = self._normalize_heading(line)
            if "СТАЖИРОВ" in normalized or "INTERNSHIP" in normalized:
                return idx
        return None

    def _clean_internship_block(self, block: list[str]) -> list[str]:
        cleaned: list[str] = []
        for line in block:
            if self._looks_like_formal_education_line(line):
                break

            line = self._prefer_internship_layout_fragment(line)
            line = self._strip_inline_heading_remainder(
                line,
                {
                    "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
                    "ОПЫТ РАБОТЫ",
                    "ОБРАЗОВАНИЕ",
                },
            )
            if not line:
                continue

            normalized = self._normalize_heading(line)
            if normalized in {
                "ОПЫТ РАБОТЫ",
                "ОБРАЗОВАНИЕ",
                "КУРСЫ",
                "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ",
                "КОНТАКТЫ",
                "О СЕБЕ",
            }:
                break

            lowered = line.lower()
            if "ооо" in lowered or re.search(r"\d{2}\.\d{2}\.\d{4}\s*-\s*", line):
                continue

            cleaned.append(line)

        return cleaned

    def _prefer_internship_layout_fragment(self, line: str) -> str:
        return self.legacy_recovery_service.prefer_noisy_internship_layout_fragment(line)

    def _strip_inline_heading_remainder(self, line: str, headings: set[str]) -> str:
        normalized = self._normalize_heading(line)
        for heading in headings:
            if normalized == heading:
                return ""
            if normalized.startswith(f"{heading} "):
                return re.sub(
                    rf"^{re.escape(heading)}\s*",
                    "",
                    line.strip(),
                    flags=re.IGNORECASE,
                ).strip()
            if re.match(rf"^{re.escape(heading)}\s*[:：-]\s*", line.strip(), flags=re.IGNORECASE):
                return re.sub(
                    rf"^{re.escape(heading)}\s*[:：-]\s*",
                    "",
                    line.strip(),
                    flags=re.IGNORECASE,
                ).strip()
        return line

    def _looks_like_formal_education_line(self, line: str) -> bool:
        return self.legacy_recovery_service.looks_like_legacy_formal_education_line(line)

    def _find_project_or_internship_start(self, lines: list[str]) -> int | None:
        markers = [
            "ПРОШЕЛ 3 СТАЖИРОВКИ",
            "ПРОШЁЛ 3 СТАЖИРОВКИ",
            "СТАЖИРОВКИ",
            "ПРОЕКТЫ",
            "ПОРТФОЛИО",
            "ACHIEVEMENTS",
            "PROJECTS",
            "INTERNSHIPS",
        ]
        for idx, line in enumerate(lines):
            normalized = self._normalize_heading(line)
            if any(marker in normalized for marker in markers):
                return idx
        return None

    def _split_numbered_signal_blocks(self, lines: list[str]) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []
        started = False

        for line in lines:
            if NUMBERED_ITEM_RE.match(line):
                started = True
                if current:
                    blocks.append(current)
                current = [NUMBERED_ITEM_RE.sub("", line).strip()]
                continue

            if not started:
                continue

            if self._looks_like_signal_stop(line):
                if current:
                    blocks.append(current)
                break

            # GENERAL: строка может заканчиваться inline section-heading
            # (напр. «…территорий (Университет)» О себе:») — это граница
            # секции, capture останавливаем, а префикс перед заголовком
            # сохраняем в текущий блок (иначе пункт N теряет хвост, а
            # следующий раздел «О себе» кровит в блок и ломает title).
            prefix, had_trailing = self._strip_trailing_section_heading(line)
            if had_trailing:
                if prefix and current:
                    current.append(prefix)
                if current:
                    blocks.append(current)
                    current = []
                break

            if current:
                current.append(line)

        if current:
            blocks.append(current)
        return blocks

    def _strip_trailing_section_heading(self, line: str) -> tuple[str, bool]:
        """Если строка заканчивается inline section-heading («… О себе:»),
        отрезать хвост-заголовок и вернуть (префикс, был-ли-заголовок).

        GENERAL-эвристика: для однословных heading'ов (ОПЫТ/НАВЫКИ/ГОРОД)
        требуем двоеточие, чтобы не отрезать «большой опыт» внутри
        предложения. Многословные (О СЕБЕ, ОПЫТ РАБОТЫ, ОБРАЗОВАНИЕ, …)
        отрезаем и без двоеточия — они однозначно секционные. Перед
        heading'ом обязан boundary-символ (пробел/кавычка/скобка/знак), чтобы
        не разрезать слово.
        """
        stripped = line.strip()
        if not stripped:
            return line, False
        # длинные heading'и первыми — чтобы «ОПЫТ РАБОТЫ» матчило раньше «ОПЫТ»
        headings = sorted(STRUCTURED_V2_SECTION_HEADINGS, key=len, reverse=True)
        for heading in headings:
            h_escaped = re.escape(heading)
            if " " in heading:
                pattern = re.compile(
                    rf"[\s»).!?\]]+\s*{h_escaped}\s*[:：-]?\s*$",
                    re.IGNORECASE,
                )
            else:
                pattern = re.compile(
                    rf"[\s»).!?\]]+\s*{h_escaped}\s*[:：]\s*$",
                    re.IGNORECASE,
                )
            match = pattern.search(stripped)
            if match:
                prefix = stripped[: match.start()].strip(" -–—•»«")
                return prefix, True
        return line, False

    def _clean_signal_title(self, lines: list[str]) -> str:
        recovered = self._recover_private_noisy_ai_signal_title_legacy(lines)
        if recovered:
            return recovered

        useful_lines = []
        for line in lines:
            if self._looks_like_layout_heading(line):
                continue
            if self._looks_like_resume_layout_noise(line):
                continue
            if self._looks_like_signal_stop(line):
                continue
            # GENERAL: убрать inline trailing section-heading («… О себе:»),
            # чтобы хвост-заголовок не попадал в title сигнала.
            line, _ = self._strip_trailing_section_heading(line)
            if line:
                useful_lines.append(line)
        title = re.sub(r"\s+", " ", " ".join(useful_lines)).strip(" -–—•")
        if ")" in title:
            title = title[: title.rfind(")") + 1].strip()
        if len(title) > 255:
            title = title[:255].rsplit(" ", 1)[0].strip()
        return title

    def _recover_private_noisy_ai_signal_title_legacy(self, lines: list[str]) -> str | None:
        return self.legacy_recovery_service.recover_noisy_ai_signal_title(lines)

    def _build_normalized_contribution_signals(
        self,
        signals: list[StructuredResumeSignal],
    ) -> list[StructuredResumeSignal]:
        normalized: list[StructuredResumeSignal] = []
        for signal in signals:
            title = re.sub(r"\s+", " ", str(signal.title or "").strip())
            if not title:
                continue
            normalized.append(
                StructuredResumeSignal(
                    title=title,
                    category=self._normalize_contribution_category(signal.category),
                    skills=self._dedupe_preserve_order(signal.skills),
                    snippet_text=signal.snippet_text or title,
                    fact_status=signal.fact_status,
                    source_type=signal.source_type,
                    source_layer="normalized_contribution_signal",
                    ownership_confidence=signal.ownership_confidence,
                    requires_confirmation=signal.requires_confirmation,
                )
            )
        return self._dedupe_signals(normalized)

    def _normalize_contribution_category(self, category: str) -> str:
        normalized = str(category or "").strip().lower()
        if normalized in {"internship", "portfolio_project", "project", "achievement"}:
            return normalized
        if normalized in {"ai_project", "automation", "prompt_engineering"}:
            return "project"
        if normalized in {"workflow_experience", "competency_signal"}:
            return "competency_signal"
        return "contribution"

    def _classify_signal_category(self, title: str, text: str) -> str:
        combined = f"{title} {text}".lower()
        if "prompt engineering" in combined or "промпт" in combined:
            return "prompt_engineering"
        if "автоматизирован" in combined or "automation" in combined or "автоматизац" in combined:
            return "automation"
        if (
            "ии" in combined
            or "искусственный интеллект" in combined
            or "llm" in combined
            or "нейро" in combined
            or "computer vision" in combined
        ):
            return "ai_project"
        if "стажиров" in combined or "internship" in combined:
            return "internship"
        if "дост" in combined or "achievement" in combined:
            return "achievement"
        return "project"

    def _extract_signal_skills(self, *texts: str) -> list[str]:
        tags = extract_skill_tags(*texts)
        display_tags = [self._display_skill_tag(tag) for tag in tags]
        return self._dedupe_preserve_order(display_tags)

    def _extract_technology_signals(self, text: str) -> list[str]:
        patterns: list[tuple[str, tuple[str, ...]]] = [
            ("AI", (r"\bai\b", r"искусственн\w+\s+интеллект")),
            ("LLM", ("llm", "языковых модел")),
            ("ChatGPT", ("chatgpt", "чат-?gpt")),
            ("prompt engineering", ("prompt engineering", "промпт")),
            (
                "computer vision",
                (
                    "computer vision",
                    "компьютерное зрени",
                    "изображени",
                    "видео",
                ),
            ),
            ("automation", ("автоматизац", "автоматизирован", "automation")),
            ("workflow", ("workflow", "workflow automation", "пайплайн", "pipeline")),
            ("Python", ("python",)),
            ("Git", ("git",)),
            ("API", ("api",)),
            ("SQL", ("sql",)),
            ("TensorFlow", ("tensorflow",)),
            ("neural networks", ("нейросет", "neural network")),
            ("Терапия", ("терап",)),
            ("Медицинская документация", ("медицинская документаци", "медицинская документ")),
            ("Клиническая диагностика", ("клиническая диагност",)),
            ("Электронные медицинские системы", ("электронные медицинск",)),
        ]
        lowered = text.lower()
        found: list[str] = []
        for label, label_patterns in patterns:
            if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in label_patterns):
                found.append(label)

        inline_skills = self._split_known_inline_skills(text)
        for skill in inline_skills:
            if skill not in found:
                found.append(skill)

        return self._dedupe_preserve_order(found)

    def _extract_competency_signals(
        self,
        lines: list[str],
        technologies: list[str],
    ) -> list[StructuredResumeSignal]:
        signals: list[StructuredResumeSignal] = []
        skills_text = self._extract_skills_summary(lines) or ""

        competency_rules = [
            (
                "AI / automation delivery",
                "competency_signal",
                {"AI", "automation", "computer vision", "LLM", "prompt engineering"},
            ),
            (
                "Workflow automation experience",
                "workflow_experience",
                {"automation", "workflow", "API"},
            ),
            (
                "Data and analytics tooling",
                "competency_signal",
                {"SQL", "TensorFlow", "Python"},
            ),
        ]
        technology_set = set(technologies)

        for title, category, required in competency_rules:
            matched = sorted(technology_set.intersection(required))
            if len(matched) >= 2:
                signals.append(
                    StructuredResumeSignal(
                        title=title,
                        category=category,
                        skills=matched,
                        snippet_text=skills_text or ", ".join(matched),
                    )
                )

        return signals

    def _display_skill_tag(self, tag: str) -> str:
        mapping = {
            "ai": "AI",
            "llm": "LLM",
            "chatgpt": "ChatGPT",
            "prompt_engineering": "prompt engineering",
            "computer_vision": "computer vision",
            "automation": "automation",
            "workflow": "workflow",
            "python": "Python",
            "fastapi": "API",
            "analytics": "analytics",
            "tensorflow": "TensorFlow",
            "sql": "SQL",
            "git": "Git",
        }
        return mapping.get(tag, tag)

    def _dedupe_signals(
        self,
        signals: list[StructuredResumeSignal],
    ) -> list[StructuredResumeSignal]:
        result: list[StructuredResumeSignal] = []
        seen: set[tuple[str, str]] = set()
        for signal in signals:
            key = (signal.title.casefold(), signal.category.casefold())
            if key in seen:
                continue
            seen.add(key)
            signal.skills = self._dedupe_preserve_order(signal.skills)
            result.append(signal)
        return result

    def _looks_like_signal_stop(self, line: str) -> bool:
        normalized = self._normalize_heading(line)
        if normalized in {
            "КУРСЫ",
            "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ",
            "О СЕБЕ",
            "КОНТАКТЫ",
        }:
            return True
        return normalized.startswith("КУРСЫ ") or normalized.startswith("ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ")

    def _looks_like_low_value_signal_title(self, title: str) -> bool:
        normalized = self._normalize_heading(title)
        if len(title) < 3:
            return True
        return (
            normalized.startswith("DATA SCIENCE")
            or "УНИВЕРСИТЕТ ИСКУССТВЕННОГО ИНТЕЛЛЕКТА" in normalized
        )

    def _looks_like_layout_heading(self, line: str) -> bool:
        return self._normalize_heading(line) in STRUCTURED_V2_SECTION_HEADINGS

    def _looks_like_resume_layout_noise(self, line: str) -> bool:
        return self.legacy_recovery_service.looks_like_legacy_resume_layout_noise(line)

    def _extract_full_name(self, lines: list[str]) -> str | None:
        candidate_parts: list[str] = []

        stop_headings = {
            "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ",
            "НАВЫКИ",
            "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
            "ОПЫТ РАБОТЫ",
            "ОБРАЗОВАНИЕ",
            "ПРОЕКТЫ",
            "СТАЖИРОВКИ",
            "КОНТАКТЫ",
            "О СЕБЕ",
        }

        for line in lines[:12]:
            if self._is_contact_or_location_line(line):
                continue

            if re.search(r"\d{2}\.\d{2}\.\d{4}", line):
                if candidate_parts:
                    break
                continue

            normalized = self._normalize_heading(line)
            if normalized in stop_headings:
                if candidate_parts:
                    break
                continue

            if not re.fullmatch(r"[A-Za-zА-Яа-яЁё -]{2,80}", line):
                if candidate_parts:
                    break
                continue

            if self._looks_like_education_identity_line(line):
                continue

            words = [part for part in re.split(r"\s+", line.strip()) if part]

            if len(candidate_parts) >= 2 and self._normalize_target_role_candidate(line) is not None:
                break

            if len(words) == 3:
                first_two = " ".join(words[:2])
                possible_role = words[2]

                if "-" in possible_role or possible_role.lower() in {
                    "developer",
                    "manager",
                    "юрист",
                    "терапевт",
                    "врач",
                }:
                    return first_two

            if 2 <= len(words) <= 3:
                return " ".join(words)

            if len(words) == 1:
                candidate_parts.append(words[0])
                continue

            if candidate_parts:
                break

        if 2 <= len(candidate_parts) <= 3:
            joined = " ".join(candidate_parts)
            if self._looks_like_education_identity_line(joined):
                return None
            return joined

        return None

    def _extract_full_name_from_top_lines(self, lines: list[str]) -> str | None:
        for line in lines[:5]:
            cleaned = line.strip()
            if not cleaned:
                continue

            if self._normalize_heading(cleaned) in {
                "ЦЕЛЕВАЯ ДОЛЖНОСТЬ",
                "ГОРОД",
                "ОПЫТ РАБОТЫ",
                "НАВЫКИ",
            }:
                continue

            parts = cleaned.split()
            if 2 <= len(parts) <= 4 and all(part[:1].isupper() for part in parts):
                return cleaned

        return None

    def _is_contact_or_location_line(self, line: str) -> bool:
        normalized = line.strip().lower()

        if not normalized:
            return True

        if "@" in normalized:
            return True

        if normalized.startswith("http://") or normalized.startswith("https://"):
            return True

        if re.search(r"\+?\d[\d\s().-]{6,}", normalized):
            return True

        if normalized.startswith("г.") or "россия" in normalized:
            return True

        if "ул." in normalized or "кв." in normalized or "д." in normalized:
            return True

        return False

    def _extract_location(self, lines: list[str]) -> str | None:
        for line in lines:
            if "Россия" in line:
                return line
            if re.match(r"^г\.\s*[A-Za-zА-Яа-яЁё-]+", line):
                return line
        return None

    def _infer_market_from_location(self, location: str) -> str | None:
        """Этап 7: эвристическое определение рынка (RU/EU/US) из location.

        Возвращает код рынка или None, если однозначно определить нельзя.
        RU-маркеры: «Россия», «г.», типичные города РФ.
        EU-маркеры: страны/столицы ЕС.
        US-маркеры: штаты/города США, «USA»/«United States».
        """
        if not location:
            return None
        text = location.lower()

        ru_markers = (
            "росси", "россия", "москва", "санкт-петербург", "спб", "новосибирск",
            "екатеринбург", "казань", "нижний новгород", "самара", "ураль",
        )
        if any(marker in text for marker in ru_markers):
            return "RU"
        if re.match(r"^\s*г\.\s*", location):
            return "RU"

        eu_markers = (
            "germany", "deutschland", "berlin", "мюнхен", "мюнхен", "france",
            "paris", "париж", "netherlands", "amsterdam", "amsterdam",
            "spain", "madrid", "italy", "rome", "рим", "sweden", "stockholm",
            "poland", "warsaw", "варшава", "european union", "еэп", "eu ",
            "austria", "vienna", "ireland", "dublin", "belgium", "brussels",
            "portugal", "lisbon", "greece", "athens", "czech", "prague", "прага",
            "finland", "helsinki", "denmark", "copenhagen", "norway", "oslo",
        )
        if any(marker in text for marker in eu_markers):
            return "EU"

        us_markers = (
            "usa", "united states", "us ", "u.s.", "new york", "san francisco",
            "california", "san jose", "seattle", "boston", "chicago", "austin",
            "denver", "washington", "texas", "florida", "remote us", "нью-йорк",
            "калифорния", "силиконовая", "силиконовая долина",
        )
        if any(marker in text for marker in us_markers):
            return "US"

        return None

    def _extract_contacts(self, lines: list[str]) -> StructuredContactDraft:
        text = "\n".join(lines)

        email = self._extract_email(text)
        phone = self._extract_phone(text)
        github = self._extract_github(text)
        telegram = self._extract_telegram(text)
        address = self._extract_address(lines)

        return StructuredContactDraft(
            email=email,
            phone=phone,
            github=github,
            telegram=telegram,
            address=address,
        )

    def _extract_email(self, text: str) -> str | None:
        match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
        return match.group(0).strip() if match else None

    def _extract_phone(self, text: str) -> str | None:
        match = re.search(r"(?:\+?\d[\d\s().-]{8,}\d)", text)
        if not match:
            return None
        return re.sub(r"\s+", " ", match.group(0)).strip()

    def _extract_github(self, text: str) -> str | None:
        match = re.search(r"https?://github\.com/[A-Za-z0-9_.-]+/?", text, re.IGNORECASE)
        return match.group(0).rstrip("/") if match else None

    def _extract_telegram(self, text: str) -> str | None:
        match = re.search(r"(?<![\w.+-])(?:https?://t\.me/[A-Za-z0-9_]+|@[A-Za-z0-9_]{5,})", text, re.IGNORECASE)
        return match.group(0).strip() if match else None

    def _extract_address(self, lines: list[str]) -> str | None:
        address_markers = ("ул.", "улица", "проспект", "пр-т", "д.", "дом", "кв.", "квартира")
        candidates = []
        for line in lines[:20]:
            lowered = line.lower()
            if any(marker in lowered for marker in address_markers):
                candidates.append(line.strip())
        return ", ".join(candidates[:2]) if candidates else None

    def _extract_target_roles(self, lines: list[str]) -> list[str]:
        section_lines = self._lines_after_heading(lines, "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ", max_lines=3)
        if not section_lines:
            section_lines = self._lines_after_heading(lines, "ЦЕЛЕВАЯ ДОЛЖНОСТЬ", max_lines=3)
        if not section_lines:
            section_lines = self._lines_after_heading(lines, "ЦЕЛЕВАЯ ПОЗИЦИЯ", max_lines=3)
        if not section_lines:
            return []

        raw_text = "\n".join(section_lines)
        raw_parts = [
            part.strip()
            for part in re.split(r"[,;|\n]+", raw_text)
            if part.strip()
        ]
        if len(raw_parts) == 1:
            raw_parts = self._split_compact_target_roles(raw_parts[0])

        roles: list[str] = []
        for raw_part in raw_parts:
            role = self._normalize_target_role_candidate(raw_part)
            if role:
                roles.append(role)

        return self._dedupe_preserve_order(roles)[:5]

    def _split_compact_target_roles(self, value: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned:
            return []

        role_starters = (
            "Слесарь",
            "Сантехник",
            "Бухгалтер",
            "Юрист",
            "Врач",
            "Инженер",
            "Менеджер",
            "Дизайнер маркетинговых",
            "Developer",
            "Engineer",
        )
        starter_pattern = "|".join(re.escape(starter) for starter in role_starters)
        parts = [
            part.strip(" .;-–—•")
            for part in re.split(
                rf"\s+(?=(?:{starter_pattern})(?:[-\s]|$))",
                cleaned,
                flags=re.IGNORECASE,
            )
            if part.strip(" .;-–—•")
        ]
        return parts if len(parts) > 1 else [cleaned]

    def _infer_headline_role_from_top_lines(
        self,
        lines: list[str],
        full_name: str | None,
    ) -> str | None:
        if not full_name:
            return None

        for idx, line in enumerate(lines[:6]):
            if line.strip() == full_name:
                for candidate in lines[idx + 1 : idx + 4]:
                    normalized = self._normalize_heading(candidate)
                    if normalized in {"ЖЕЛАЕМАЯ ДОЛЖНОСТЬ", "ЦЕЛЕВАЯ ДОЛЖНОСТЬ", "ГОРОД"}:
                        continue
                    if normalized in STRUCTURED_V2_SECTION_HEADINGS:
                        return None
                    if self._is_contact_or_location_line(candidate):
                        continue
                    cleaned = re.sub(r"\s+", " ", candidate.strip())
                    if 3 <= len(cleaned) <= 80:
                        return cleaned
        return None

    def _normalize_target_role_candidate(self, value: str) -> str | None:
        cleaned = re.sub(r"^\d+[.)]\s*", "", value.strip())
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -–—•")

        if not cleaned:
            return None

        english_fragments = [
            match.group(0).strip()
            for match in re.finditer(
                r"[A-Za-z][A-Za-z+#./-]*(?:\s+[A-Za-z][A-Za-z+#./-]*){0,3}",
                cleaned,
            )
        ]

        if english_fragments:
            best_fragment = max(english_fragments, key=len)
            if len(best_fragment) >= 3:
                return best_fragment

        if self._looks_like_target_role_noise(cleaned):
            return None

        words = cleaned.split()
        if 1 <= len(words) <= 6 and len(cleaned) <= 80:
            return cleaned

        return None

    def _looks_like_target_role_noise(self, value: str) -> bool:
        return self.legacy_recovery_service.looks_like_legacy_target_role_noise(value)

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            key = value.casefold()
            if key in seen:
                continue

            seen.add(key)
            result.append(value)

        return result

    def _extract_skills_summary(self, lines: list[str]) -> str | None:
        section = self._extract_section(
            lines,
            start_heading="ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ",
            stop_headings={
                "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
                "ОПЫТ РАБОТЫ",
                "ОБРАЗОВАНИЕ",
                "ПРОЕКТЫ",
                "СТАЖИРОВКИ",
                "КОНТАКТЫ",
            },
        )

        if not section:
            section = self._extract_section(
                lines,
                start_heading="КЛЮЧЕВЫЕ НАВЫКИ",
                stop_headings={
                    "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
                    "ОПЫТ РАБОТЫ",
                    "ОБРАЗОВАНИЕ",
                    "ПРОЕКТЫ",
                    "СТАЖИРОВКИ",
                    "КОНТАКТЫ",
                },
            )

        if not section:
            section = self._extract_section(
                lines,
                start_heading="НАВЫКИ",
                stop_headings={
                    "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
                    "ОПЫТ РАБОТЫ",
                    "ОБРАЗОВАНИЕ",
                    "ПРОЕКТЫ",
                    "СТАЖИРОВКИ",
                    "КОНТАКТЫ",
                },
            )

        if not section:
            return None

        def strip_inline_skill_tail(value: str) -> str:
            return re.split(
                r"\s+(?:образование|опыт работы|опыт|курсы|проекты|стажировки|контакты|достижения|о себе)\s*[:：]",
                value,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()

        skill_lines: list[str] = []
        for line in section:
            normalized_heading = self._normalize_heading(line)
            if normalized_heading in {
                "ОБРАЗОВАНИЕ",
                "ОПЫТ",
                "ОПЫТ РАБОТЫ",
                "КУРСЫ",
                "ПРОЕКТЫ",
                "СТАЖИРОВКИ",
                "КОНТАКТЫ",
                "ДОСТИЖЕНИЯ",
                "О СЕБЕ",
            }:
                break

            if NUMBERED_ITEM_RE.match(line):
                break
            lowered = line.lower()
            if "стажиров" in lowered:
                continue
            cleaned = re.sub(
                r"\s+направлению\s+data\s+science\s*:?\s*$",
                "",
                line.strip(),
                flags=re.IGNORECASE,
            ).strip()
            cleaned = strip_inline_skill_tail(cleaned)
            if cleaned:
                if re.fullmatch(r"[•\s\d]+", cleaned):
                    continue
                if re.fullmatch(r"\d+", cleaned):
                    continue
                skill_lines.append(cleaned)

        expanded_skill_lines = self._extract_inline_skills_from_lines(skill_lines)

        summary = "\n".join(expanded_skill_lines[:12]).strip()
        return summary or None

    def _extract_experiences(self, lines: list[str]) -> list[StructuredExperienceDraft]:
        section = self._extract_section(
            lines,
            start_heading="ОПЫТ РАБОТЫ",
            stop_headings={
                "ОБРАЗОВАНИЕ",
                "О СЕБЕ",
                "КУРСЫ",
                "СТАЖИРОВКИ",
                "НАВЫКИ",
                "КЛЮЧЕВЫЕ НАВЫКИ",
            },
        )
        if not section:
            section = self._extract_section(
                lines,
                start_heading="ОПЫТ",
                stop_headings={
                    "ОБРАЗОВАНИЕ",
                    "О СЕБЕ",
                    "КУРСЫ",
                    "СТАЖИРОВКИ",
                    "НАВЫКИ",
                    "КЛЮЧЕВЫЕ НАВЫКИ",
                },
            )
        if not section:
            return []

        section = self._normalize_experience_section_lines(section)
        multiline_experiences = self._extract_multiline_experiences(section)
        if multiline_experiences:
            return multiline_experiences

        blocks: list[list[str]] = []
        current: list[str] = []

        for line in section:
            current.append(line)
            if INLINE_DATE_RANGE_RE.search(line):
                blocks.append(current)
                current = []

        experiences: list[StructuredExperienceDraft] = []

        for idx, block in enumerate(blocks):
            date_line = next((line for line in reversed(block) if INLINE_DATE_RANGE_RE.search(line)), None)
            if date_line is None:
                continue

            date_match = INLINE_DATE_RANGE_RE.search(date_line)
            date_prefix = ""
            if date_match:
                date_prefix = date_line[: date_match.start()].strip(" -–—•")

            info_source_lines = [line for line in block if line != date_line]
            if date_prefix:
                info_source_lines.append(date_prefix)

            info_lines = self._clean_experience_info_lines(info_source_lines)
            if not info_lines:
                continue

            company, role = self._split_company_and_role(info_lines)
            start_date, end_date = self._parse_date_range(date_line)

            responsibility_lines = self._extract_resume_subsection(
                lines,
                start_heading="ОБЯЗАННОСТИ",
                stop_headings={
                    "ДОСТИЖЕНИЯ",
                    "НАВЫКИ",
                    "ОБРАЗОВАНИЕ",
                    "О СЕБЕ",
                    "КУРСЫ",
                    "СТАЖИРОВКИ",
                    "ПРОЕКТЫ",
                },
            )

            description_parts = self._split_inline_responsibility_items(responsibility_lines)

            description_raw = "\n".join(description_parts).strip() or " ".join(info_lines).strip() or None

            if self._normalize_heading(company) in {"ОБЯЗАННОСТИ", "ДОСТИЖЕНИЯ"}:
                continue
            if len(role) > 255:
                continue

            if company and role:
                experiences.append(
                    StructuredExperienceDraft(
                        company=company,
                        role=role,
                        start_date=start_date,
                        end_date=end_date,
                        description_raw=description_raw,
                        order_index=idx,
                    )
                )

        return experiences

    def _extract_multiline_experiences(
        self,
        lines: list[str],
    ) -> list[StructuredExperienceDraft]:
        date_indices = [
            idx
            for idx, line in enumerate(lines)
            if MONTH_YEAR_DATE_RANGE_RE.match(line.strip())
        ]
        if not date_indices:
            return []

        experiences: list[StructuredExperienceDraft] = []
        stop_headings = {
            "ДОСТИЖЕНИЯ",
            "НАВЫКИ",
            "КЛЮЧЕВЫЕ НАВЫКИ",
            "ОБРАЗОВАНИЕ",
            "ОПЫТ",
            "ОПЫТ РАБОТЫ",
            "КУРСЫ",
            "СТАЖИРОВКИ",
            "ПРОЕКТЫ",
            "О СЕБЕ",
            # Bug#12: новые секции, часто идущие сразу после опыта.
            # Без них парсер тянет в description_raw текст следующей
            # секции (мусор «в пВХ оконных изделий обслуживанию
            # электрооборудования по изображениям и» — склейка блоков).
            "ПРАКТИЧЕСКИЙ ОПЫТ",
            "ДОПОЛНИТЕЛЬНОЕ ОБУЧЕНИЕ",
            "ДОПОЛНИТЕЛЬНО",
            "ВАЖНОЕ ПОЗИЦИОНИРОВАНИЕ",
            "ЦЕЛЬ",
            "КОНТАКТЫ",
            "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ",
        }
        label_headings = {"КОМПАНИЯ", "ДОЛЖНОСТЬ", "ПЕРИОД", "ДАТА"}

        for order_index, date_index in enumerate(date_indices):
            company, role = self._find_company_role_before_date(lines, date_index)
            if not company or not role:
                continue

            period_line = lines[date_index].strip()

            if self._normalize_heading(company) in label_headings or self._normalize_heading(role) in label_headings:
                continue
            if not self._looks_like_company_line(company):
                if self._looks_like_company_line(role) and self._looks_like_role_line(company):
                    company, role = role, company
                else:
                    continue
            if self._looks_like_company_line(role):
                continue

            start_date, end_date = self._parse_date_range(period_line)
            if start_date is None and end_date is None:
                continue

            if order_index + 1 < len(date_indices):
                next_date_index = date_indices[order_index + 1]
                next_company, _ = self._find_company_role_before_date(lines, next_date_index)

                stop_index = next_date_index
                if next_company:
                    for idx in range(date_index + 1, next_date_index):
                        if lines[idx].strip() == next_company:
                            stop_index = idx
                            break
            else:
                stop_index = len(lines)
            stop_index = max(date_index + 1, stop_index)

            responsibility_lines: list[str] = []
            for line in lines[date_index + 1 : stop_index]:
                normalized = self._normalize_heading(line)
                if any(
                    normalized == heading or normalized.startswith(f"{heading} ")
                    for heading in stop_headings
                ):
                    break

                cleaned_line = self._strip_inline_heading_remainder(line, {"ОБЯЗАННОСТИ"})
                cleaned_line = re.sub(r"\s+", " ", cleaned_line).strip(" .;-–—•")
                if cleaned_line:
                    responsibility_lines.append(cleaned_line)

            description_parts = self._split_inline_responsibility_items(responsibility_lines)
            description_raw = "\n".join(description_parts).strip() or " ".join(
                part for part in (company, role) if part
            ).strip() or None

            experiences.append(
                StructuredExperienceDraft(
                    company=company,
                    role=role,
                    start_date=start_date,
                    end_date=end_date,
                    description_raw=description_raw,
                    order_index=order_index,
                )
            )

        return experiences

    def _find_company_role_before_date(
        self,
        lines: list[str],
        date_index: int,
    ) -> tuple[str | None, str | None]:
        candidates: list[str] = []

        skip_headings = {
            "ОБЯЗАННОСТИ",
            "ДОСТИЖЕНИЯ",
            "НАВЫКИ",
            "КЛЮЧЕВЫЕ НАВЫКИ",
            "ОБРАЗОВАНИЕ",
            "ОПЫТ",
            "ОПЫТ РАБОТЫ",
        }

        for index in range(date_index - 1, max(-1, date_index - 8), -1):
            value = re.sub(r"\s+", " ", lines[index]).strip(" .;-–—•")
            if not value:
                continue
            normalized = self._normalize_heading(value)
            if normalized in skip_headings:
                continue
            if self._line_has_contribution_signal(value):
                continue
            candidates.append(value)

            if len(candidates) >= 4:
                break

        candidates = list(reversed(candidates))

        for candidate in candidates:
            inline_company, inline_role = self._split_inline_company_role(candidate)
            if inline_company and inline_role:
                return inline_company, inline_role

        for idx in range(len(candidates) - 1):
            company_candidate = candidates[idx]
            role_candidate = candidates[idx + 1]

            if (
                self._looks_like_company_line(company_candidate)
                and self._looks_like_role_line(role_candidate)
                and not self._looks_like_company_line(role_candidate)
            ):
                return company_candidate, role_candidate

        return None, None

    def _normalize_experience_section_lines(self, lines: list[str]) -> list[str]:
        normalized_lines: list[str] = []

        for line in lines:
            value = re.sub(r"\s+", " ", str(line or "")).strip()
            if not value:
                continue

            embedded_match = re.match(
                r"^(?P<company>(?:ООО|АО|ПАО|ЗАО|МУП|ГБУ|ИП)\s+«[^»]+»)\s+(?P<role>.+)$",
                value,
                flags=re.IGNORECASE,
            )
            if embedded_match:
                company = embedded_match.group("company").strip()
                role = embedded_match.group("role").strip()
                if company:
                    normalized_lines.append(company)
                if role:
                    normalized_lines.append(role)
                continue

            normalized_lines.append(value)

        return normalized_lines

    def _split_inline_company_role(self, value: str) -> tuple[str | None, str | None]:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        if not text:
            return None, None

        legal_form_pattern = r"(?:ООО|ОАО|АО|ЗАО|ПАО|ИП|МУП|ГУП|ФГБУ|ГБУ|МКУ|МБУ)"
        match = re.match(
            rf"^(?P<company>{legal_form_pattern}\s+[«\"A-ZА-ЯЁ0-9][^,;]*?)\s+"
            r"(?P<role>(?:слесарь[-\s])?сантехник|бухгалтер|старший бухгалтер|юрист|врач[-\s]\w+|[A-Za-z ]+developer|[A-Za-z ]+engineer)$",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None, None

        company = match.group("company").strip(" .;-–—•")
        role = match.group("role").strip(" .;-–—•")
        return company, role

    def _clean_experience_info_lines(self, info_lines: list[str]) -> list[str]:
        has_numbered_layout_noise = any(NUMBERED_ITEM_RE.match(line) for line in info_lines)
        cleaned: list[str] = []

        for line in info_lines:
            value = line.strip()
            if not value:
                continue

            if has_numbered_layout_noise:
                if NUMBERED_ITEM_RE.match(value):
                    continue
                if re.fullmatch(r"\(?\s*ООО\s+.+\)?", value, flags=re.IGNORECASE):
                    continue
                value = re.split(r"\s{2,}", value, maxsplit=1)[0].strip()

            if value:
                cleaned.append(value)

        return cleaned

    def _dedupe_education_strings(self, items: list[str]) -> list[str]:
        """GENERAL дедуп образователь. Один вуз мог попасть дважды — с
        патронимом/локацией («… им. И.И. Ползунова, Барнаул») и без
        («… университет»). Сравниваем по корню названия (отрезаем
        «им./имени X» и хвост после первой запятой) и оставляем более
        подробный вариант. Не использует хардкоды конкретных вузов."""
        result: list[str] = []
        roots: dict[str, int] = {}
        for item in items:
            root = self._education_institution_root(item)
            if not root:
                result.append(item)
                continue
            idx = roots.get(root)
            if idx is None:
                roots[root] = len(result)
                result.append(item)
                continue
            if len(item) > len(result[idx]):
                result[idx] = item
        return result

    def _education_institution_root(self, value: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
        # отрезать от « им.»/«имени »/первой запятой — патроним и локация,
        # не ядро названия учреждения
        text = re.split(r"\s+им(?:ени)?\.?\s+|,", text, maxsplit=1)[0].strip()
        return text

    def _extract_education(self, lines: list[str]) -> list[StructuredEducationDraft]:
        section = self._extract_section(
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

        current: list[str] = []
        for line in section:
            normalized = self._normalize_heading(line)
            lowered = line.lower()
            if "СТАЖИРОВ" in normalized:
                continue
            has_education_marker = any(
                marker in lowered
                for marker in (
                    "университет",
                    "институт",
                    "колледж",
                    "техникум",
                    "академия",
                    "специальность",
                    "бакалавр",
                    "магистр",
                    "высшее",
                    "среднее",
                )
            )
            if self._looks_like_resume_layout_noise(line) and not has_education_marker:
                continue
            current.append(line)

        if not current:
            return []

        known_items = self._extract_known_formal_education_lines(" ".join(current))
        if known_items:
            return [
                StructuredEducationDraft(
                    institution=item,
                    details=item,
                )
                for item in self._dedupe_education_strings(known_items)
            ]

        institution = None
        specialty = None
        degree = None
        period = None

        for line in current:
            lowered = line.lower()

            if re.search(r"\b(19|20)\d{2}\b", line):
                period = line.strip()

            if any(
                marker in lowered
                for marker in ("университет", "институт", "колледж", "техникум", "академия")
            ):
                institution = line.strip()

            if any(
                marker in lowered
                for marker in ("бакалавр", "магистр", "специалист", "среднее", "высшее")
            ):
                degree = line.strip()

            if any(
                marker in lowered
                for marker in (
                    "специальность",
                    "программное обеспечение",
                    "вычислительной техники",
                )
            ):
                specialty = re.sub(
                    r"^специальность\s*:?\s*",
                    "",
                    line.strip(),
                    flags=re.IGNORECASE,
                )

        if institution or specialty or degree:
            details = "; ".join(current[:4])
            if self._looks_like_mixed_education_layout_noise(details):
                return []
            return [
                StructuredEducationDraft(
                    institution=institution or "Учебное заведение не указано",
                    degree=degree,
                    specialty=specialty,
                    period=period,
                    details="; ".join(current[:4]),
                )
            ]

        return []

    def _extract_courses(self, lines: list[str]) -> list[StructuredResumeSignal]:
        section = self._extract_section(
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
        education_section = self._extract_section(
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
        known_course_titles = self._extract_known_course_lines(" ".join([*section, *education_section]))
        if known_course_titles:
            return self._dedupe_signals(
                [
                    StructuredResumeSignal(title=line, category="course", snippet_text=line)
                    for line in known_course_titles
                ]
            )

        signals = [
            StructuredResumeSignal(title=line, category="course", snippet_text=line)
            for line in [*known_course_titles, *section]
            if not self._looks_like_resume_layout_noise(line)
            and not self._looks_like_layout_heading(line)
            and not self._looks_like_mixed_education_layout_noise(line)
        ]
        return self._dedupe_signals(signals)

    def _extract_known_formal_education_lines(self, value: str) -> list[str]:
        return self.legacy_recovery_service.recover_known_formal_education_lines(value)

    def _extract_known_course_lines(self, value: str) -> list[str]:
        return self.legacy_recovery_service.recover_known_course_lines(value)

    def _looks_like_mixed_education_layout_noise(self, value: str) -> bool:
        return self.legacy_recovery_service.looks_like_legacy_mixed_education_layout_noise(value)

    def _split_company_and_role(self, info_lines: list[str]) -> tuple[str, str]:
        combined = " ".join(info_lines).strip()

        if "," in combined:
            company, role = combined.split(",", 1)
            return company.strip(), role.strip()

        if len(info_lines) == 1:
            words = combined.split()
            for split_index in range(len(words) - 1, 0, -1):
                company_candidate = " ".join(words[:split_index]).strip()
                role_candidate = " ".join(words[split_index:]).strip()
                normalized_role = self._normalize_target_role_candidate(role_candidate)
                if company_candidate and normalized_role:
                    return company_candidate, normalized_role

        company = info_lines[0].strip()
        role = " ".join(info_lines[1:]).strip()

        return company, role

    def _parse_date_range(self, value: str) -> tuple[date | None, date | None]:
        month_year_match = MONTH_YEAR_DATE_RANGE_RE.search(value)
        if month_year_match:
            start_raw = month_year_match.group("start")
            end_raw = month_year_match.group("end")
            start_month, start_year = start_raw.split(".")
            start_date = date(int(start_year), int(start_month), 1)

            if end_raw.lower() in {"настоящее время", "н.в."}:
                return start_date, None

            end_month, end_year = end_raw.split(".")
            last_day = monthrange(int(end_year), int(end_month))[1]
            end_date = date(int(end_year), int(end_month), last_day)
            return start_date, end_date

        match = INLINE_DATE_RANGE_RE.search(value)
        if not match:
            return None, None

        start_raw = match.group("start")
        end_raw = match.group("end")

        if len(start_raw) == 4 and start_raw.isdigit():
            start_date = date(int(start_raw), 1, 1)
        elif len(start_raw) == 7 and re.fullmatch(r"\d{2}\.\d{4}", start_raw):
            start_month, start_year = start_raw.split(".")
            start_date = date(int(start_year), int(start_month), 1)
        else:
            start_date = datetime.strptime(start_raw, "%d.%m.%Y").date()

        if end_raw.lower() in {"по настоящее время", "настоящее время", "н.в."}:
            return start_date, None

        if len(end_raw) == 4 and end_raw.isdigit():
            end_date = date(int(end_raw), 12, 31)
            return start_date, end_date

        if len(end_raw) == 7 and re.fullmatch(r"\d{2}\.\d{4}", end_raw):
            end_month, end_year = end_raw.split(".")
            last_day = monthrange(int(end_year), int(end_month))[1]
            end_date = date(int(end_year), int(end_month), last_day)
            return start_date, end_date

        end_date = datetime.strptime(end_raw, "%d.%m.%Y").date()
        return start_date, end_date

    def _extract_section(
        self,
        lines: list[str],
        *,
        start_heading: str,
        stop_headings: set[str],
    ) -> list[str]:
        capture = False
        section: list[str] = []

        for line in lines:
            normalized = self._normalize_heading(line)

            if normalized == start_heading or normalized.startswith(f"{start_heading} "):
                capture = True
                remainder = re.sub(
                    rf"^{re.escape(start_heading)}\s*[:：-]?\s*",
                    "",
                    line.strip(),
                    flags=re.IGNORECASE,
                ).strip()
                if remainder:
                    section.append(remainder)
                continue

            if capture and any(
                normalized == heading or normalized.startswith(f"{heading} ")
                for heading in stop_headings
            ):
                break

            if capture:
                section.append(line)

        return section

    def _extract_resume_subsection(
        self,
        lines: list[str],
        *,
        start_heading: str,
        stop_headings: set[str],
    ) -> list[str]:
        section: list[str] = []
        capture = False

        for line in lines:
            normalized = self._normalize_heading(line)

            if normalized == start_heading:
                capture = True
                continue

            if capture and normalized in stop_headings:
                break

            if capture:
                cleaned = line.strip(" -–—•")
                if cleaned:
                    section.append(cleaned)

        return section

    def _split_inline_responsibility_items(self, lines: list[str]) -> list[str]:
        starters = (
            "Ведение",
            "Работа с",
            "Сверка",
            "Подготовка",
            "Работа в",
            "Участие",
            "Контроль",
            "Проверка",
            "Формирование",
            "Архивация",
            "Выполнение",
            "Взаимодействие",
            "Координация",
            "Оформление",
            "Монтаж",
            "Обслуживание",
            "Замена",
            "Устранение",
            "Установка",
            "Проведение",
            "Ремонт",
            "Профилактическое",
        )

        starter_pattern = "|".join(re.escape(starter) for starter in starters)

        result: list[str] = []
        for line in lines:
            cleaned = re.sub(r"\s+", " ", str(line or "")).strip(" .;-–—•")
            if not cleaned:
                continue

            parts = [
                part.strip(" .;-–—•")
                for part in re.split(
                    rf"\s+(?=(?:{starter_pattern})(?:\s|$))",
                    cleaned,
                    flags=re.IGNORECASE,
                )
                if part.strip(" .;-–—•")
            ]

            result.extend(parts if len(parts) > 1 else [cleaned])

        return self._dedupe_preserve_order(result)

    def _lines_after_heading(
        self,
        lines: list[str],
        heading: str,
        *,
        max_lines: int = 1,
    ) -> list[str]:
        for idx, line in enumerate(lines):
            if self._normalize_heading(line) == heading:
                result: list[str] = []
                for candidate in lines[idx + 1 :]:
                    normalized = self._normalize_heading(candidate)
                    if normalized in STRUCTURED_V2_SECTION_HEADINGS:
                        break
                    result.append(candidate)
                    if len(result) >= max_lines:
                        break
                return result
        return []

    def _normalize_heading(self, value: str) -> str:
        cleaned = re.sub(r"[:：]+$", "", value.strip())
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.upper()

    def _looks_like_company_line(self, value: str) -> bool:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            return False

        return bool(re.search(
            r"(?:^|\s)(ООО|АО|ПАО|ЗАО|МУП|ГБУ|ИП)\s+|«[^»]+»",
            text,
            flags=re.IGNORECASE,
        ))

    def _line_has_contribution_signal(self, value: str) -> bool:
        lowered = re.sub(r"\s+", " ", str(value or "")).strip().lower()
        if not lowered:
            return False

        contribution_markers = (
            "обязанност",
            "достижен",
            "разработал",
            "разработала",
            "снизил",
            "снизила",
            "сократил",
            "сократила",
            "ускорил",
            "ускорила",
            "улучшил",
            "улучшила",
            "внедрил",
            "внедрила",
            "оптимизировал",
            "оптимизировала",
            "создал",
            "создала",
            "контрол",
            "управлен",
            "организац",
            "переговор",
            "закуп",
            "поставщик",
            "договор",
            "бюджет",
        )
        return any(marker in lowered for marker in contribution_markers)

    def _looks_like_role_line(self, value: str) -> bool:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        if not text or self._looks_like_company_line(text):
            return False
        if self._line_has_achievement_like_action(text):
            return False

        lowered = text.lower()
        role_markers = (
            "сантехник",
            "слесарь",
            "бухгалтер",
            "юрист",
            "врач",
            "менеджер",
            "developer",
            "engineer",
            "project manager",
            "supervisor",
        )
        return any(marker in lowered for marker in role_markers) or len(text.split()) <= 4

    def _line_has_achievement_like_action(self, value: str) -> bool:
        lowered = str(value or "").strip().lower()
        action_markers = (
            "разработал",
            "разработала",
            "сократил",
            "сократила",
            "снизил",
            "снизила",
            "ускорил",
            "ускорила",
            "улучшил",
            "улучшила",
            "внедрил",
            "внедрила",
            "создал",
            "создала",
            "оптимизировал",
            "оптимизировала",
        )
        return any(lowered.startswith(marker) for marker in action_markers)

    def _split_inline_achievement_items(self, value: str) -> list[str]:
        action_starters = (
            "Снизил",
            "Снизила",
            "Сократил",
            "Сократила",
            "Разработал",
            "Разработала",
            "Ускорил",
            "Ускорила",
            "Улучшил",
            "Улучшила",
            "Внедрил",
            "Внедрила",
            "Создал",
            "Создала",
            "Оптимизировал",
            "Оптимизировала",
        )
        starter_pattern = "|".join(re.escape(starter) for starter in action_starters)
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        parts = [
            part.strip(" .;-–—•")
            for part in re.split(
                rf"\s+(?=(?:{starter_pattern})(?:\s|$))",
                cleaned,
                flags=re.IGNORECASE,
            )
            if part.strip(" .;-–—•")
        ]
        return parts or ([cleaned] if cleaned else [])

    def _strip_company_suffix_from_achievement_text(self, value: str) -> str:
        """
        PR-37: Отрезает суффиксы компаний (ООО, АО, ПАО, МУП, ГБУ и т.д.) из конца achievement title.
        Обрабатывает форматы:
        - Разработал чек-лист МУП «Горводоканал»
        - Снизил затраты ООО «ТехКомСервис»
        - Разработал модуль (ООО «Рога и Копыта»)
        """
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")

        # PR-37: Паттерн для захвата company suffix в конце строки
        # Захватывает: пробел/скобка + юр.форма + название (до закрывающей скобки или конца строки)
        match = re.search(
            r'[\s(]+((?:ООО|АО|ПАО|МУП|ГБУ|ОАО|ЗАО|ИП|ГУП|ФГБУ|МКУ|МБУ)\s+[^)]+)\)?$',
            cleaned,
            flags=re.IGNORECASE,
        )
        if match:
            before = cleaned[: match.start()].strip(" .;-–—•")
            return before if before else cleaned
        
        return cleaned

    def _split_inline_resume_headings(self, lines: list[str]) -> list[str]:
        result: list[str] = []

        heading_patterns = [
            "Целевая должность",
            "Целевая позиция",
            "Краткое резюме",
            "Ключевые навыки",
            "Ключевые достижения",
            "Город",
            "Опыт",
            "Опыт работы",
            "Обязанности",
            "Достижения",
            "Навыки",
            "Профессиональные навыки",
            "Образование",
            "Курсы",
            "Проекты",
            "Портфолио",
            "Стажировки",
        ]

        for line in lines:
            current = line.strip()
            if not current:
                continue

            for heading in sorted(heading_patterns, key=len, reverse=True):
                prefix_guard = ""
                suffix_guard = ""
                if heading == "Опыт":
                    suffix_guard = r"(?!\s+работы\b)"
                elif heading == "Навыки":
                    prefix_guard = r"(?<!ключевые\s)(?<!профессиональные\s)"
                elif heading == "Достижения":
                    prefix_guard = r"(?<!ключевые\s)"
                current = re.sub(
                    rf"(?<!^)(?<!\n)\s+{prefix_guard}({re.escape(heading)}){suffix_guard}(?=\s*[:：]|\s+(?-i:[A-ZА-ЯЁ0-9]))",
                    r"\n\1",
                    current,
                    flags=re.IGNORECASE,
                )

            for heading in sorted(heading_patterns, key=len, reverse=True):
                prefix_guard = ""
                suffix_guard = ""
                if heading == "Опыт":
                    suffix_guard = r"(?!\s+работы\b)"
                elif heading == "Навыки":
                    prefix_guard = r"(?<!ключевые\s)(?<!профессиональные\s)"
                elif heading == "Достижения":
                    prefix_guard = r"(?<!ключевые\s)"
                current = re.sub(
                    rf"(?im)^{prefix_guard}({re.escape(heading)}){suffix_guard}(?=\s*[:：]|\s+(?-i:[A-ZА-ЯЁ0-9]))(?:\s*[:：])?\s+(.+)$",
                    r"\1\n\2",
                    current,
                    flags=re.IGNORECASE,
                )

            for part in current.splitlines():
                cleaned_part = part.strip()
                if not cleaned_part:
                    continue
                result.extend(self._split_company_suffix_from_achievement_line(cleaned_part))

        return result

    def _split_company_suffix_from_achievement_line(self, line: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", str(line or "")).strip()
        if not cleaned:
            return []

        legal_form_pattern = r"(?:ООО|ОАО|АО|ЗАО|ПАО|ИП|МУП|ГУП|ФГБУ|ГБУ|МКУ|МБУ)"
        match = re.search(
            rf"\s+({legal_form_pattern}\s+[«\"A-ZА-ЯЁ0-9][^.!?]*)$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            return [cleaned]

        before = self._strip_company_suffix_from_achievement_text(cleaned)
        company = match.group(1).strip(" .;-–—•")
        if not before or before == cleaned or not self._line_has_achievement_like_action(before):
            return [cleaned]
        if not self._looks_like_company_line(company):
            return [cleaned]

        return [before, company]

    def _extract_name_and_headline_from_compact_first_line(
        self,
        lines: list[str],
    ) -> tuple[str | None, str | None]:
        if not lines:
            return None, None

        first = re.sub(r"\s+", " ", lines[0]).strip()
        first = re.split(r"\bОпыт\s*[:：]", first, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        words = first.split()

        if len(words) < 3 or len(words) > 6:
            return None, None

        first_two = " ".join(words[:2])
        rest = " ".join(words[2:])

        if not re.fullmatch(r"[A-ZА-ЯЁ][a-zа-яё-]+ [A-ZА-ЯЁ][a-zа-яё-]+", first_two):
            return None, None

        if len(rest) < 3 or len(rest) > 80:
            return None, None

        if len(words) == 3 and self._looks_like_third_name_token(rest):
            return None, None

        return first_two, rest

    def _looks_like_third_name_token(self, value: str) -> bool:
        cleaned = value.strip()
        if "-" in cleaned:
            return False
        if not re.fullmatch(r"[А-ЯЁ][а-яё-]+", cleaned):
            return False

        known_single_word_roles = {
            "администратор",
            "аналитик",
            "бухгалтер",
            "водитель",
            "врач",
            "дизайнер",
            "инженер",
            "кассир",
            "маркетолог",
            "менеджер",
            "продавец",
            "разработчик",
            "сантехник",
            "слесарь",
            "сварщик",
            "терапевт",
            "электрик",
            "юрист",
        }
        return cleaned.casefold() not in known_single_word_roles

    def _looks_like_education_identity_line(self, value: str) -> bool:
        lowered = value.lower()
        return any(
            marker in lowered
            for marker in (
                "ранхигс",
                "университет",
                "институт",
                "академия",
                "колледж",
                "техникум",
                "менеджмент",
                "юриспруденция",
                "лечебное дело",
                "прикладная информатика",
            )
        )

    def _split_known_inline_skills(self, value: str) -> list[str]:
        known_skills = [
            # accounting / admin
            "1С:Бухгалтерия",
            "1С 8.3",
            "Первичная документация",
            "Сверка взаиморасчётов",
            "Банк-клиент",
            "Excel",
            "НДС",
            "Акты сверки",
            "Деловая переписка",
            "Контур",
            "Умная Логистика",
            "Архивация документов",
            "Платежные поручения",

            # management / warehouse
            "Складская логистика",
            "Управление персоналом",
            "Контроль качества",
            "WMS",
            "1С",

            # trades / maintenance
            "Монтаж систем водоснабжения",
            "Канализация",
            "Отопление",
            "Ремонт трубопроводов",
            "Сантехническое оборудование",
            "Чтение технических схем",
            "Сварочные работы",
            "Работа с электроинструментом",

            # IT / product
            "Stakeholder Management",
            "Project Management",
            "FastAPI",
            "API",
            "PostgreSQL",
            "SQL",
            "SQLAlchemy",
            "Pytest",
            "Python",
            "LLM",
            "Docker",
            "Redis",
            "Git",
            "Tensorflow",
            "Agile",
            "Scrum",
            "Kanban",
            "Jira",
            "Confluence",
        ]

        text = re.sub(r"\s+", " ", value).strip()
        found_with_positions: list[tuple[int, str]] = []

        for skill in sorted(known_skills, key=len, reverse=True):
            match = re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", text, flags=re.IGNORECASE)
            if match:
                found_with_positions.append((match.start(), skill))

        found = [skill for _, skill in sorted(found_with_positions, key=lambda item: item[0])]
        return self._dedupe_preserve_order(found)

    def _extract_inline_skills_from_lines(self, lines: list[str]) -> list[str]:
        result: list[str] = []

        for line in lines:
            candidate = line.strip()
            candidate = re.split(
                r"\s+(?:образование|опыт работы|опыт|курсы|проекты|стажировки|контакты|достижения|о себе)\s*[:：]",
                candidate,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            if not candidate:
                continue

            inline_skills = self._split_known_inline_skills(candidate)
            if len(inline_skills) >= 2:
                result.extend(inline_skills)
                continue

            compact_parts = self._split_compact_skill_line(candidate)
            if len(compact_parts) >= 2:
                result.extend(compact_parts)
                continue

            comma_parts = [
                part.strip(" .;:-–—•")
                for part in re.split(r"[,;|]", candidate)
                if part.strip(" .;:-–—•")
            ]
            if len(comma_parts) >= 2:
                result.extend(comma_parts)
                continue

            result.append(candidate)

        return self._dedupe_preserve_order(result)

    def _split_compact_skill_line(self, value: str) -> list[str]:
        known_skills = [
            "Медицинская документация",
            "Клиническая диагностика",
            "Электронные медицинские системы",
            "Терапия",
            "Амбулаторный прием",
            "Амбулаторный приём",
            "Экстренная медицинская помощь",
            "Предрейсовые осмотры",
            "Послерейсовые осмотры",
            "Медицинское освидетельствование",
            "Монтаж систем водоснабжения",
            "Канализация",
            "Отопление",
            "Ремонт трубопроводов",
            "Сантехническое оборудование",
            "Чтение технических схем",
            "Сварочные работы",
            "Работа с электроинструментом",
        ]

        remaining = value.strip()
        result: list[str] = []

        for skill in known_skills:
            pattern = rf"(?<!\w){re.escape(skill)}(?!\w)"
            if re.search(pattern, remaining, flags=re.IGNORECASE):
                result.append(skill)
                remaining = re.sub(pattern, "\n", remaining, flags=re.IGNORECASE)

        for part in re.split(r"[\n,;|]+", remaining):
            cleaned = part.strip(" .;:-–—•")
            if cleaned:
                result.append(cleaned)

        return self._dedupe_preserve_order(result)
