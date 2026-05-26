# app\services\profile_structuring_service.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
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
from app.services.evidence_strength_service import EvidenceStrengthService


DATE_RANGE_RE = re.compile(
    r"(?P<start>\d{2}\.\d{2}\.\d{4})\s*-\s*(?P<end>по настоящее время|\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)
NUMBERED_ITEM_RE = re.compile(r"^\d{1,2}\s*[.)\-–—:]\s+")
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")


STRUCTURED_V2_SECTION_HEADINGS = {
    "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ",
    "НАВЫКИ",
    "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
    "ОПЫТ РАБОТЫ",
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
class StructuredResumeSignal:
    title: str
    category: str
    skills: list[str] = field(default_factory=list)
    snippet_text: str | None = None
    fact_status: str = "user_provided"

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "category": self.category,
            "skills": list(self.skills),
            "snippet_text": self.snippet_text or self.title,
            "fact_status": self.fact_status,
        }


@dataclass
class StructuredProfileDraft:
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    summary: str | None = None
    target_roles: list[str] = field(default_factory=list)
    experiences: list[StructuredExperienceDraft] = field(default_factory=list)
    projects: list[StructuredResumeSignal] = field(default_factory=list)
    internships: list[StructuredResumeSignal] = field(default_factory=list)
    achievements: list[StructuredResumeSignal] = field(default_factory=list)
    ai_tools: list[str] = field(default_factory=list)
    automation_tools: list[str] = field(default_factory=list)
    workflow_experience: list[StructuredResumeSignal] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    evidence_snippets: list[StructuredResumeSignal] = field(default_factory=list)
    competency_signals: list[StructuredResumeSignal] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ProfileStructuringService:
    def __init__(
        self,
        file_extraction_repository: FileExtractionRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        evidence_snippet_repository: EvidenceSnippetRepository | None = None,
        evidence_strength_service: EvidenceStrengthService | None = None,
    ) -> None:
        self.file_extraction_repository = file_extraction_repository or FileExtractionRepository()
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.evidence_snippet_repository = (
            evidence_snippet_repository or EvidenceSnippetRepository()
        )
        self.evidence_strength_service = evidence_strength_service or EvidenceStrengthService()

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

        if extraction.source_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="source file for extraction not found",
            )

        draft = self._build_draft(extraction.extracted_text)

        profile = await self.candidate_profile_repository.get_by_user_id(
            session,
            user_id,
        )
        if profile is None:
            profile = await self.candidate_profile_repository.create_empty(
                session,
                user_id=user_id,
            )

        self._apply_profile_fields(profile, draft)
        await self._replace_experiences(session, profile.id, draft.experiences)
        await self._upsert_structured_evidence(session, user_id=user_id, draft=draft)

        await session.flush()
        await session.refresh(profile)
        return profile, draft

    def _build_draft(self, text: str) -> StructuredProfileDraft:
        lines = self._clean_lines(text)
        draft = StructuredProfileDraft()

        draft.full_name = self._extract_full_name(lines)
        draft.location = self._extract_location(lines)
        draft.summary = self._extract_skills_summary(lines)
        draft.target_roles = self._extract_target_roles(lines)
        draft.headline = ", ".join(draft.target_roles[:3]) if draft.target_roles else None
        draft.experiences = self._extract_experiences(lines)
        self._apply_structured_resume_v2(lines, draft)

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
                        source_type="resume_structured",
                        skills=skills,
                        fact_status=signal.fact_status,
                    ),
                    "title": signal.title,
                    "snippet_text": snippet_text,
                    "source_type": "resume_structured",
                    "skills": skills,
                    "evidence_strength": str(strength),
                    "fact_status": signal.fact_status,
                    "usage_count": 0,
                    "used_in_documents_count": 0,
                    "used_in_interviews_count": 0,
                    "star_summary": {
                        "category": signal.category,
                        "source": "structured_resume_extraction_v2",
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
    ) -> None:
        text = "\n".join(lines)
        project_signals = self._extract_project_like_signals(lines)
        technology_signals = self._extract_technology_signals(text)
        competency_signals = self._extract_competency_signals(lines, technology_signals)

        draft.projects = [
            signal
            for signal in project_signals
            if signal.category in {"project", "ai_project", "automation", "prompt_engineering"}
        ]
        draft.internships = [
            signal
            for signal in project_signals
            if signal.category == "internship"
        ]
        draft.achievements = [
            signal
            for signal in project_signals
            if signal.category == "achievement"
        ]
        draft.workflow_experience = [
            signal
            for signal in project_signals + competency_signals
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

        evidence_candidates = project_signals + competency_signals
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

            if current:
                current.append(line)

        if current:
            blocks.append(current)
        return blocks

    def _clean_signal_title(self, lines: list[str]) -> str:
        recovered = self._recover_known_ai_signal_title(lines)
        if recovered:
            return recovered

        useful_lines = [
            line
            for line in lines
            if not self._looks_like_layout_heading(line)
            and not self._looks_like_resume_layout_noise(line)
            and not self._looks_like_signal_stop(line)
        ]
        title = re.sub(r"\s+", " ", " ".join(useful_lines)).strip(" -–—•")
        if ")" in title:
            title = title[: title.rfind(")") + 1].strip()
        if len(title) > 255:
            title = title[:255].rsplit(" ", 1)[0].strip()
        return title

    def _recover_known_ai_signal_title(self, lines: list[str]) -> str | None:
        text = re.sub(r"\s+", " ", " ".join(lines)).strip()
        lowered = text.lower()

        if "создание ии-системы" in lowered:
            if "мониторинг" in lowered and "пожил" in lowered:
                return "ИИ-система мониторинга безопасности"
            return "Создание ИИ-системы"
        if "автоматизирован" in lowered and "ии-контроль качества" in lowered:
            return "Автоматизированный ИИ-контроль качества"
        if "prompt engineering" in lowered or "промпт" in lowered:
            return "Prompt Engineering"
        if "ии-анализ" in lowered and "отзыв" in lowered:
            return "ИИ-анализ текстовых отзывов"
        return None

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
            ("AI", (r"\bai\b", r"\bии\b", r"искусственн\w+\s+интеллект")),
            ("LLM", (r"\bllm\b", r"языков\w+\s+модел")),
            ("ChatGPT", (r"\bchatgpt\b", r"чат[\s-]?gpt")),
            ("prompt engineering", (r"prompt engineering", r"промпт")),
            (
                "computer vision",
                (
                    r"computer vision",
                    r"компьютерн\w+\s+зрени",
                    r"изображени",
                    r"\bвидео\b",
                ),
            ),
            ("automation", (r"автоматизац", r"автоматизирован", r"\bautomation\b")),
            ("workflow", (r"\bworkflow\b", r"процесс", r"пайплайн", r"\bpipeline\b")),
            ("Python", (r"\bpython\b",)),
            ("Git", (r"\bgit\b",)),
            ("API", (r"\bapi\b",)),
            ("SQL", (r"\bsql\b",)),
            ("TensorFlow", (r"\btensorflow\b",)),
            ("neural networks", (r"нейросет", r"neural network")),
        ]
        lowered = text.lower()
        found: list[str] = []
        for label, label_patterns in patterns:
            if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in label_patterns):
                found.append(label)
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
        normalized = self._normalize_heading(line)
        if re.search(r"\d{2}\.\d{2}\.\d{4}\s*-\s*", line):
            return True
        if re.match(r"^\d{4}\b", line.strip()):
            return True
        return any(
            marker in normalized
            for marker in {
                "АЛТАЙСКИЙ ГОСУДАРСТВЕННЫЙ",
                "МЕДИЦИНСКИЙ УНИВЕРСИТЕТ",
                "УНИВЕРСИТЕТ ИМЕНИ",
                "ЭЛЕКТРОМОНТЕР",
                "ОБСЛУЖИВАНИЮ ЭЛЕКТРООБОРУДОВАНИЯ",
                "ИНЖЕНЕР,",
                "АВТОМОБИЛЕ- И ТРАКТОРОСТРОЕНИЕ",
                "РЯЗАНСКОЕ ВЫСШЕЕ",
                "ВОЗДУШНО-ДЕСАНТНОЕ",
            }
        )

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

            words = [part for part in re.split(r"\s+", line.strip()) if part]

            if 2 <= len(words) <= 3:
                return " ".join(words)

            if len(words) == 1:
                candidate_parts.append(words[0])
                continue

            if candidate_parts:
                break

        if 2 <= len(candidate_parts) <= 3:
            return " ".join(candidate_parts)

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

    def _extract_target_roles(self, lines: list[str]) -> list[str]:
        section_lines = self._lines_after_heading(lines, "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ", max_lines=3)
        if not section_lines:
            return []

        raw_text = " ".join(section_lines)
        raw_parts = [part.strip() for part in re.split(r"[,;|]", raw_text) if part.strip()]

        roles: list[str] = []
        for raw_part in raw_parts:
            role = self._normalize_target_role_candidate(raw_part)
            if role:
                roles.append(role)

        return self._dedupe_preserve_order(roles)[:5]

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
        lowered = value.lower()

        noise_markers = {
            "мониторинг",
            "безопасности",
            "пансионат",
            "пожилых",
            "создание",
            "системы",
            "качества",
            "изделий",
            "изображениям",
            "видео",
            "отзывов",
            "населения",
            "объектах",
            "инфраструктуры",
            "прогнозирования",
            "университет",
            "ооо",
        }

        return any(marker in lowered for marker in noise_markers)

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

        summary = "\n".join(section[:8]).strip()
        return summary or None

    def _extract_experiences(self, lines: list[str]) -> list[StructuredExperienceDraft]:
        section = self._extract_section(
            lines,
            start_heading="ОПЫТ РАБОТЫ",
            stop_headings={"ОБРАЗОВАНИЕ", "О СЕБЕ", "КУРСЫ", "СТАЖИРОВКИ"},
        )
        if not section:
            return []

        blocks: list[list[str]] = []
        current: list[str] = []

        for line in section:
            current.append(line)
            if DATE_RANGE_RE.search(line):
                blocks.append(current)
                current = []

        experiences: list[StructuredExperienceDraft] = []

        for idx, block in enumerate(blocks):
            date_line = next((line for line in reversed(block) if DATE_RANGE_RE.search(line)), None)
            if date_line is None:
                continue

            info_lines = [line for line in block if line != date_line]
            if not info_lines:
                continue

            company, role = self._split_company_and_role(info_lines)
            start_date, end_date = self._parse_date_range(date_line)

            description_raw = " ".join(info_lines).strip() or None

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

    def _split_company_and_role(self, info_lines: list[str]) -> tuple[str, str]:
        combined = " ".join(info_lines).strip()

        if "," in combined:
            company, role = combined.split(",", 1)
            return company.strip(), role.strip()

        company = info_lines[0].strip()
        role = " ".join(info_lines[1:]).strip()

        return company, role

    def _parse_date_range(self, value: str) -> tuple[date | None, date | None]:
        match = DATE_RANGE_RE.search(value)
        if not match:
            return None, None

        start_raw = match.group("start")
        end_raw = match.group("end")

        start_date = datetime.strptime(start_raw, "%d.%m.%Y").date()

        if end_raw.lower() == "по настоящее время":
            return start_date, None

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

            if normalized == start_heading:
                capture = True
                continue

            if capture and normalized in stop_headings:
                break

            if capture:
                section.append(line)

        return section

    def _lines_after_heading(
        self,
        lines: list[str],
        heading: str,
        *,
        max_lines: int = 1,
    ) -> list[str]:
        for idx, line in enumerate(lines):
            if self._normalize_heading(line) == heading:
                return lines[idx + 1 : idx + 1 + max_lines]
        return []

    def _normalize_heading(self, value: str) -> str:
        cleaned = re.sub(r"[:：]+$", "", value.strip())
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.upper()
