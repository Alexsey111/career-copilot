# app\services\profile_structuring_service.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateExperience, CandidateProfile
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.file_extraction_repository import FileExtractionRepository


DATE_RANGE_RE = re.compile(
    r"(?P<start>\d{2}\.\d{2}\.\d{4})\s*-\s*(?P<end>по настоящее время|\d{2}\.\d{2}\.\d{4})",
    re.IGNORECASE,
)


@dataclass
class StructuredExperienceDraft:
    company: str
    role: str
    start_date: date | None
    end_date: date | None
    description_raw: str | None
    order_index: int


@dataclass
class StructuredProfileDraft:
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    summary: str | None = None
    target_roles: list[str] = field(default_factory=list)
    experiences: list[StructuredExperienceDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ProfileStructuringService:
    def __init__(
        self,
        file_extraction_repository: FileExtractionRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
    ) -> None:
        self.file_extraction_repository = file_extraction_repository or FileExtractionRepository()
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
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

        if not draft.full_name:
            draft.warnings.append("full_name was not extracted confidently")
        if not draft.target_roles:
            draft.warnings.append("target roles were not extracted")
        if not draft.experiences:
            draft.warnings.append("work experience section was not parsed")

        draft.warnings.append(
            "contacts, achievements, metrics and proof-status mapping are not extracted in v1"
        )

        return draft

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
        return [line.strip() for line in text.splitlines() if line.strip()]

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
