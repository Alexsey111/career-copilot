# app\services\achievement_extraction_service.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateProfile
from app.repositories.candidate_achievement_repository import CandidateAchievementRepository
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.file_extraction_repository import FileExtractionRepository


NUMBERED_ITEM_RE = re.compile(r"^\d{1,2}\s*[.)\-–—:]\s*")
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")


@dataclass
class AchievementDraft:
    title: str
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metric_text: str | None = None
    evidence_note: str | None = None
    fact_status: str = "needs_confirmation"


@dataclass
class AchievementExtractionResult:
    profile: CandidateProfile
    achievements: list[AchievementDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AchievementExtractionService:
    def __init__(
        self,
        file_extraction_repository: FileExtractionRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        candidate_achievement_repository: CandidateAchievementRepository | None = None,
    ) -> None:
        self.file_extraction_repository = file_extraction_repository or FileExtractionRepository()
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.candidate_achievement_repository = (
            candidate_achievement_repository or CandidateAchievementRepository()
        )

    async def extract_achievements(
        self,
        session: AsyncSession,
        *,
        extraction_id: UUID,
        user_id: UUID,
    ) -> AchievementExtractionResult:
        extraction = await self.file_extraction_repository.get_by_id(session, extraction_id)
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

        if extraction.source_file.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="file extraction not found",
            )

        profile = await self.candidate_profile_repository.get_by_user_id(
            session,
            extraction.source_file.user_id,
        )
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="candidate profile not found; run structured profile extraction first",
            )

        drafts, warnings = self._build_achievement_drafts(extraction.extracted_text)

        created_items = await self.candidate_achievement_repository.replace_for_profile(
            session,
            profile_id=profile.id,
            achievements=[
                {
                    "title": draft.title,
                    "situation": draft.situation,
                    "task": draft.task,
                    "action": draft.action,
                    "result": draft.result,
                    "metric_text": draft.metric_text,
                    "evidence_note": draft.evidence_note,
                    "fact_status": draft.fact_status,
                    "experience_id": None,
                }
                for draft in drafts
            ],
        )

        await session.commit()

        return AchievementExtractionResult(
            profile=profile,
            achievements=[
                AchievementDraft(
                    title=item.title,
                    situation=item.situation,
                    task=item.task,
                    action=item.action,
                    result=item.result,
                    metric_text=item.metric_text,
                    evidence_note=item.evidence_note,
                    fact_status=item.fact_status,
                )
                for item in created_items
            ],
            warnings=warnings,
        )

    def _build_achievement_drafts(self, text: str) -> tuple[list[AchievementDraft], list[str]]:
        lines = self._clean_lines(text)
        warnings: list[str] = []

        section_start = self._find_projects_start(lines)
        if section_start is None:
            warnings.append("no internship/project section detected confidently")
            return [], warnings

        candidate_lines = lines[section_start + 1 :]
        blocks = self._split_numbered_blocks(candidate_lines)

        if not blocks:
            warnings.append("no numbered achievement blocks were extracted")
            return [], warnings

        drafts: list[AchievementDraft] = []

        for block in blocks:
            title = self._clean_achievement_title(block)
            if not title:
                continue

            if self._looks_like_noise_title(title):
                continue

            drafts.append(
                AchievementDraft(
                    title=title,
                    evidence_note=(
                        "Auto-extracted from resume raw text; requires user confirmation "
                        "before strong use in documents."
                    ),
                    fact_status="needs_confirmation",
                )
            )

        if not drafts:
            warnings.append("all extracted achievement candidates were filtered as low-confidence")
            return [], warnings

        warnings.append(
            "titles were extracted conservatively; metrics/results were not inferred in v1"
        )

        return drafts, warnings

    def _clean_lines(self, text: str) -> list[str]:
        cleaned_lines: list[str] = []
        for raw_line in text.splitlines():
            line = ZERO_WIDTH_RE.sub("", raw_line).strip()
            if line:
                cleaned_lines.append(line)
        return cleaned_lines

    def _find_projects_start(self, lines: list[str]) -> int | None:
        markers = [
            "ПРОШЕЛ 3 СТАЖИРОВКИ",
            "ПРОШЁЛ 3 СТАЖИРОВКИ",
            "СТАЖИРОВКИ",
            "ПРОЕКТЫ",
            "ПОРТФОЛИО",
        ]

        for idx, line in enumerate(lines):
            normalized = self._normalize(line)
            if any(marker in normalized for marker in markers):
                return idx

        return None

    def _split_numbered_blocks(self, lines: list[str]) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []
        started = False

        for line in lines:
            if self._is_numbered_item(line):
                started = True
                if current:
                    blocks.append(current)
                current = [self._strip_numbering(line)]
                continue

            if not started:
                continue

            if self._looks_like_achievement_stop(line):
                if current:
                    blocks.append(current)
                    current = []
                break

            if current:
                current.append(line)

        if current:
            blocks.append(current)

        return blocks

    def _clean_achievement_title(self, lines: list[str]) -> str:
        useful_lines: list[str] = []

        for line in lines:
            if self._looks_like_achievement_stop(line):
                break
            useful_lines.append(line)

        title = re.sub(r"\s+", " ", " ".join(part.strip() for part in useful_lines if part.strip()))
        title = title.strip()

        # ???? ???? ??????????? ??????, ??????? ??? ???????????? ???????? ???????:
        # "... (??? ?...?) [?????? ?????]" -> ????? ?? ????????? ')'
        if ")" in title:
            title = title[: title.rfind(")") + 1].strip()

        # ?????? ?? ??????? ???????? title
        if len(title) > 255:
            title = title[:255].rsplit(" ", 1)[0].strip()

        return title

    def _looks_like_noise_title(self, title: str) -> bool:
        normalized = self._normalize(title)

        if re.match(r"^\d{4}\b", title):
            return True

        if normalized.startswith("DATA SCIENCE"):
            return True

        if "УНИВЕРСИТЕТ ИСКУССТВЕННОГО ИНТЕЛЛЕКТА" in normalized:
            return True

        if "PYTHON С НУЛЯ" in normalized:
            return True

        if "АНАЛИТИК ДАННЫХ" in normalized and "(" not in title:
            return True

        return False

    def _is_numbered_item(self, line: str) -> bool:
        return bool(NUMBERED_ITEM_RE.match(line))

    def _strip_numbering(self, line: str) -> str:
        return NUMBERED_ITEM_RE.sub("", line).strip()

    def _looks_like_achievement_stop(self, line: str) -> bool:
        normalized = self._normalize(line)

        stop_headings = {
            "ОБРАЗОВАНИЕ",
            "ОПЫТ РАБОТЫ",
            "КОНТАКТЫ",
            "НАВЫКИ",
            "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ",
            "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
        }
        if normalized in stop_headings:
            return True

        # Строки с годом в начале — у тебя это уже ушло в шумный 4-й achievement
        if re.match(r"^\d{4}\b", line.strip()):
            return True

        # Курсы / доп. обучение после блока стажировок
        if "УНИВЕРСИТЕТ ИСКУССТВЕННОГО ИНТЕЛЛЕКТА" in normalized:
            return True

        if "PYTHON С НУЛЯ" in normalized:
            return True

        if "АНАЛИТИК ДАННЫХ" in normalized:
            return True

        return False

    def _normalize(self, line: str) -> str:
        return re.sub(r"\s+", " ", line.strip()).upper()
