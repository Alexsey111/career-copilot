# app\services\achievement_extraction_service.py

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contribution import NormalizedContributionSignal, ReviewedCandidateOwnership
from app.domain.evidence import extract_skill_tags
from app.models import CandidateProfile
from app.repositories.candidate_achievement_repository import CandidateAchievementRepository
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.file_extraction_repository import FileExtractionRepository
from app.services.core_service_policy import LEGACY_CANDIDATE_SPECIFIC_HEURISTIC
from app.services.legacy_resume_recovery_service import LegacyResumeRecoveryService


NUMBERED_ITEM_RE = re.compile(r"^\d{1,2}\s*[.)\-–—:]\s+")
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")

CONTRIBUTION_ACTION_VERBS = (
    "Сократил",
    "Сократила",
    "Снизил",
    "Снизила",
    "Ускорил",
    "Ускорила",
    "Улучшил",
    "Улучшила",
    "Внедрил",
    "Внедрила",
    "Создал",
    "Создала",
    "Навел",
    "Навела",
    "Подготовил",
    "Подготовила",
    "Разработал",
    "Разработала",
    "Участвовал",
    "Участвовала",
    "Провёл",
    "Провел",
    "Провела",
    "Перевёл",
    "Перевел",
    "Перевела",
    "Настроил",
    "Настроила",
    "Оптимизировал",
    "Оптимизировала",
    "Автоматизировал",
    "Автоматизировала",
    "Мигрировал",
    "Мигрировала",
    "Рефакторил",
    "Модернизировал",
)


@dataclass
class AchievementDraft:
    title: str
    id: UUID | None = None
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metric_text: str | None = None
    evidence_note: str | None = None
    fact_status: str = "needs_confirmation"
    ownership_confidence: str = "low"
    requires_confirmation: bool = True


@dataclass
class AchievementExtractionResult:
    profile: CandidateProfile
    achievements: list[AchievementDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AchievementExtractionService:
    legacy_private_recovery_marker = LEGACY_CANDIDATE_SPECIFIC_HEURISTIC

    def __init__(
        self,
        file_extraction_repository: FileExtractionRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        candidate_achievement_repository: CandidateAchievementRepository | None = None,
        enable_legacy_recovery: bool = True,
    ) -> None:
        self.file_extraction_repository = file_extraction_repository or FileExtractionRepository()
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.candidate_achievement_repository = (
            candidate_achievement_repository or CandidateAchievementRepository()
        )
        self.legacy_recovery_service = LegacyResumeRecoveryService(
            enabled=enable_legacy_recovery,
        )

    async def extract_achievements(
        self,
        session: AsyncSession,
        *,
        extraction_id: UUID,
        user_id: UUID,
    ) -> AchievementExtractionResult:
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

        profile = await self.candidate_profile_repository.get_by_user_id(
            session,
            user_id,
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
                    "ownership_confidence": draft.ownership_confidence,
                    "requires_confirmation": draft.requires_confirmation,
                    "experience_id": None,
                }
                for draft in drafts
            ],
        )

        return AchievementExtractionResult(
            profile=profile,
            achievements=[
                AchievementDraft(
                    title=item.title,
                    id=item.id,
                    situation=item.situation,
                    task=item.task,
                    action=item.action,
                    result=item.result,
                    metric_text=item.metric_text,
                    evidence_note=item.evidence_note,
                    fact_status=item.fact_status,
                    ownership_confidence="low",
                    requires_confirmation=True,
                )
                for item in created_items
            ],
            warnings=warnings,
        )

    def _build_achievement_drafts(self, text: str) -> tuple[list[AchievementDraft], list[str]]:
        signals, warnings = self.extract_contribution_signals_for_review(text)

        if not signals:
            return [], warnings

        reviewed = self._build_reviewed_candidate_ownership(signals)
        drafts = self._achievement_drafts_from_reviewed_ownership(reviewed)

        return drafts, warnings

    def extract_contribution_signals_for_review(
        self,
        text: str,
    ) -> tuple[list[NormalizedContributionSignal], list[str]]:
        signals = self._extract_normalized_contribution_signals(text)

        if not signals:
            return [], ["no contribution signals detected confidently"]

        return signals, [
            "normalized contribution signals were extracted; candidate ownership requires review"
        ]

    def _extract_normalized_contribution_signals(
        self,
        text: str,
    ) -> list[NormalizedContributionSignal]:
        lines = self._clean_lines(text)
        if not lines:
            return []

        blocks = self._select_contribution_blocks(lines)

        signals: list[NormalizedContributionSignal] = []
        for block in blocks:
            title = self._strip_inline_layout_heading_tail(
                self._clean_contribution_title(block)
            )
            source_text = self._build_contribution_source_text(block)
            titles = self._split_inline_contribution_items(title)
            for split_title in titles:
                if (
                    not split_title
                    or self._looks_like_noise_title(split_title)
                    or self._looks_like_invalid_contribution_title(split_title)
                    or self._looks_like_responsibility_like_contribution(split_title, source_text)
                ):
                    continue

                signals.append(
                    NormalizedContributionSignal(
                        title=split_title,
                        contribution_type=self._classify_contribution_type(split_title, source_text),
                        source_text=source_text or split_title,
                        skills=self._extract_contribution_skills(split_title, source_text),
                        confidence="medium",
                        ownership_confidence="low",
                        requires_confirmation=True,
                        source_layer="generic_extraction",
                    )
                )

        return self._dedupe_contribution_signals(signals)

    def _looks_like_invalid_contribution_title(self, title: str) -> bool:
        cleaned = re.sub(r"\s+", " ", str(title or "")).strip(" .;-–—•")
        if not cleaned:
            return True
        if len(cleaned) < 4:
            return True
        if re.fullmatch(r"\d+", cleaned):
            return True
        return False

    def _build_reviewed_candidate_ownership(
        self,
        signals: list[NormalizedContributionSignal],
    ) -> list[ReviewedCandidateOwnership]:
        return [
            ReviewedCandidateOwnership(signal=signal)
            for signal in signals
        ]

    def _achievement_drafts_from_reviewed_ownership(
        self,
        reviewed_items: list[ReviewedCandidateOwnership],
    ) -> list[AchievementDraft]:
        return [
            AchievementDraft(
                title=item.signal.title,
                evidence_note=item.reviewer_note,
                fact_status=item.fact_status,
                ownership_confidence=item.ownership_confidence,
                requires_confirmation=item.requires_confirmation,
            )
            for item in reviewed_items
        ]

    def _select_contribution_blocks(self, lines: list[str]) -> list[list[str]]:
        """Выбирает блоки строк, из которых будут извлечены achievement-сигналы.

        Приоритет:

        1. Явный раздел достижений/проектов/стажировок — наиболее надёжный
           сигнал; ограничиваем поиск строками после этого заголовка.
        2. Нет явного раздела, но есть нумерованный список. В двухколоночных
           резюме такой список (стажировки/проекты) часто расположен в колонке
           «Профессиональные навыки» ВЫШЕ раздела «ОПЫТ РАБОТЫ». Если ограничить
           поиск fallback-маркером «ОПЫТ», эти пункты будут отброшены — поэтому
           нумерованные блоки ищутся по всему тексту.
        3. Fallback на prose-поиск от раздела «ОПЫТ», чтобы не подтягивать
           контакты, образование и курсы в резюме без списков.
        """
        preferred_start = self._find_preferred_contribution_section_start(lines)
        if preferred_start is not None:
            return self._split_contribution_blocks(lines[preferred_start + 1 :])

        numbered = self._split_numbered_blocks(lines)
        if numbered:
            return numbered

        fallback_start = self._find_fallback_contribution_section_start(lines)
        candidate_lines = lines[fallback_start + 1 :] if fallback_start is not None else lines
        return self._split_contribution_blocks(candidate_lines)

    def _find_preferred_contribution_section_start(self, lines: list[str]) -> int | None:
        return self._find_section_start(lines, self._preferred_contribution_markers())

    def _find_fallback_contribution_section_start(self, lines: list[str]) -> int | None:
        return self._find_section_start(lines, self._fallback_contribution_markers())

    def _preferred_contribution_markers(self) -> tuple[str, ...]:
        return (
            "КЛЮЧЕВЫЕ ДОСТИЖЕНИЯ",
            "ДОСТИЖЕНИЯ",
            "РЕЗУЛЬТАТЫ",
            "ACHIEVEMENTS",
            "KEY ACHIEVEMENTS",
            "ПРОЕКТЫ",
            "РЕЛЕВАНТНЫЕ ПРОЕКТЫ",
            "PROJECTS",
            "ПОРТФОЛИО",
            "PORTFOLIO",
            "СТАЖИРОВКИ",
            "INTERNSHIPS",
        )

    def _fallback_contribution_markers(self) -> tuple[str, ...]:
        return (
            "ОПЫТ",
            "EXPERIENCE",
        )

    def _find_section_start(self, lines: list[str], markers: tuple[str, ...]) -> int | None:
        for idx, line in enumerate(lines):
            normalized = self._normalize(line)
            if any(marker in normalized for marker in markers):
                return idx
        return None

    def _split_contribution_blocks(self, lines: list[str]) -> list[list[str]]:
        numbered_blocks = self._split_numbered_blocks(lines)
        if numbered_blocks:
            return numbered_blocks

        bullet_blocks: list[list[str]] = []
        for line in lines:
            if self._looks_like_hard_achievement_stop(line):
                break
            if re.match(r"^\s*[-•]\s+", line):
                cleaned = self._strip_inline_layout_heading_tail(
                    re.sub(r"^\s*[-•]\s+", "", line).strip()
                )
                if self._looks_like_resume_layout_noise(cleaned):
                    continue
                if cleaned:
                    for item in self._split_inline_contribution_items(cleaned):
                        bullet_blocks.append([item])
        if bullet_blocks:
            return bullet_blocks

        section_lines = [
            line
            for line in lines
            if not self._looks_like_layout_heading(line)
            and not self._looks_like_hard_achievement_stop(line)
            and not self._looks_like_resume_layout_noise(line)
        ]
        section_lines = self._trim_lines_after_company_boundary(section_lines)
        contribution_lines = [
            line
            for line in section_lines
            if self._line_has_contribution_signal(line)
        ]
        if len(contribution_lines) >= 2:
            return [[line] for line in contribution_lines[:6]]
        if section_lines and self._line_has_contribution_signal(" ".join(section_lines)):
            return [section_lines[:6]]
        return []

    def _split_inline_contribution_items(self, value: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" ;-–—•")
        if not cleaned:
            return []

        split_starters = list(CONTRIBUTION_ACTION_VERBS)
        starter_pattern = "|".join(re.escape(starter) for starter in split_starters)
        split_by_starters = [
            part.strip(" ;-–—•")
            for part in re.split(
                rf"\s+(?=(?:{starter_pattern})(?:\s|$))",
                cleaned,
                flags=re.IGNORECASE,
            )
            if part.strip(" ;-–—•")
        ]

        if len(split_by_starters) >= 2 and all(
            self._line_has_contribution_signal(part)
            for part in split_by_starters
        ):
            return split_by_starters

        # Split only when dash likely separates two achievement-like clauses.
        parts = [
            part.strip(" ;-–—•")
            for part in re.split(r"\s+-\s+", cleaned)
            if part.strip(" ;-–—•")
        ]

        if len(parts) <= 1:
            return [cleaned]

        achievement_like_parts = [
            part
            for part in parts
            if self._line_has_contribution_signal(part)
            and not self._looks_like_responsibility_like_contribution(part, part)
        ]

        if len(achievement_like_parts) >= 2:
            return achievement_like_parts

        return [cleaned]

    def _strip_inline_layout_heading_tail(self, value: str) -> str:
        cleaned = str(value or "").strip()

        inline_headings = (
            "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ",
            "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
            "ОПЫТ РАБОТЫ",
            "ОБРАЗОВАНИЕ",
            "НАВЫКИ",
            "КОНТАКТЫ",
            "КУРСЫ",
        )

        for heading in inline_headings:
            cleaned = re.sub(
                rf"\s+{re.escape(heading)}\s*[:：].*$",
                "",
                cleaned,
                flags=re.IGNORECASE,
            ).strip()

        cleaned = re.sub(
            r"\s+(профессиональные\s+навыки|желаемая\s+должность|опыт\s+работы|образование|навыки|контакты|курсы)\s*[:：]?\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()

        return cleaned

    def _build_contribution_source_text(self, block: list[str]) -> str:
        """Собирает source_text блока, вычищая layout-заголовки так же,
        как это делает ``_clean_contribution_title`` для title.

        Раньше source_text собирался прямым ``" ".join(block)`` и тащил
        внутрь layout-заголовки, вклеенные в блок при склейке двух колонок
        PDF (например, «Желаемая должность»). Это ломало responsibility-фильтр
        (маркер «должност») и classify/skills-экстракцию мусором. Title уже
        чистился, source_text — нет; теперь оба формируются из одного набора
        отфильтрованных строк.
        """
        parts: list[str] = []
        for line in block:
            if self._looks_like_layout_heading(line):
                continue
            if self._looks_like_resume_layout_noise(line):
                continue
            cleaned = self._strip_inline_noise(line)
            if cleaned.strip():
                parts.append(cleaned.strip())
        joined = re.sub(r"\s+", " ", " ".join(parts)).strip()
        return self._strip_inline_layout_heading_tail(joined)

    def _clean_contribution_title(self, lines: list[str]) -> str:
        recovered = self._recover_private_noisy_ai_achievement_title_legacy(lines)
        if recovered:
            return recovered

        useful_lines: list[str] = []

        for line in lines:
            if self._looks_like_layout_heading(line):
                continue
            if self._looks_like_hard_achievement_stop(line):
                break
            if self._looks_like_resume_layout_noise(line):
                continue
            useful_lines.append(self._strip_inline_noise(line))

        title = re.sub(r"\s+", " ", " ".join(part.strip() for part in useful_lines if part.strip()))
        title = title.strip(" -–—•")

        sentence_match = re.match(r"^(.{12,180}?[.!?])\s+", title)
        if sentence_match:
            title = sentence_match.group(1).strip()

        if ")" in title and title.rfind(")") < 160:
            title = title[: title.rfind(")") + 1].strip()

        if len(title) > 180:
            title = title[:180].rsplit(" ", 1)[0].strip()

        return self._strip_inline_company_tail(title)

    def _strip_inline_company_tail(self, title: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(title or "")).strip(" -–—•")
        if not cleaned:
            return cleaned

        legal_forms = (
            "ООО",
            "ОАО",
            "АО",
            "ЗАО",
            "ПАО",
            "ИП",
            "МУП",
            "ГУП",
            "ФГБУ",
            "ГБУ",
            "МКУ",
            "МБУ",
            "НКО",
            "АНО",
            "LLC",
            "LTD",
            "INC",
            "CORP",
        )
        legal_form_pattern = "|".join(re.escape(value) for value in legal_forms)
        match = re.search(
            rf"\s+(?P<form>{legal_form_pattern})\s+[«\"A-Za-zА-Яа-яЁё].*$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            return cleaned

        prefix = cleaned[: match.start()].rstrip(" -–—•")
        previous_word = prefix.rsplit(" ", 1)[-1].casefold() if prefix else ""
        if previous_word in {"для", "в", "во", "на", "у"}:
            return cleaned
        return prefix or cleaned

    def _strip_inline_noise(self, line: str) -> str:
        text = line.strip()
        for marker in ("ОПЫТ РАБОТЫ", "ОБРАЗОВАНИЕ", "КУРСЫ", "CONTACTS", "EDUCATION"):
            parts = re.split(rf"\b{re.escape(marker)}\b", text, flags=re.IGNORECASE)
            if len(parts) > 1:
                text = parts[0].strip() or parts[-1].strip()
        return text

    def _classify_contribution_type(self, title: str, source_text: str) -> str:
        text = f"{title} {source_text}".lower()
        if any(marker in text for marker in ("стажиров", "internship")):
            return "internship"
        if any(marker in text for marker in ("проект", "project", "portfolio")):
            return "project"
        if any(
            marker in text
            for marker in (
                "достиж",
                "achievement",
                "result",
                "reduced",
                "improved",
                "prepared",
                "negotiated",
                "увелич",
                "сократ",
                "подготов",
                "соглас",
            )
        ):
            return "achievement"
        if any(marker in text for marker in ("managed", "coordinated", "led", "руковод", "координир")):
            return "operational_contribution"
        return "contribution"

    def _looks_like_responsibility_like_contribution(self, title: str, source_text: str) -> bool:
        text = re.sub(r"\s+", " ", f"{title} {source_text}").strip().lower()

        if not text:
            return False

        if self._line_has_contribution_signal(text):
            return False

        if re.search(r"\d", text) or "%" in text:
            return False

        responsibility_markers = (
            "обязанност",
            "responsibilit",
            "должност",
            "функц",
            "ведение",
            "обслуживан",
            "сопровожд",
            "координац",
            "управлен",
            "поддержк",
            "проведени",
            "проводил",
            "взаимодейств",
            "участв",
            "работа с",
            "осуществл",
            "выполнял",
            "консульт",
            "осмотр",
            "проверк",
            "подготовк",
            "документирован",
            "обработк",
        )
        return any(marker in text for marker in responsibility_markers)

    def _extract_contribution_skills(self, title: str, source_text: str) -> list[str]:
        tags = extract_skill_tags(title, source_text)
        return self._dedupe_preserve_order(
            [tag.replace("_", " ").title() if tag.islower() else tag for tag in tags]
        )

    def _line_has_contribution_signal(self, text: str) -> bool:
        lowered = text.lower()
        markers = (
            "разработ",
            "создал",
            "запуст",
            "провел",
            "провёл",
            "реализ",
            "сниз",
            "сократ",
            "ускор",
            "увелич",
            "улучш",
            "внедр",
            "навел",
            "навёл",
            "подготов",
            "участв",
            "managed",
            "built",
            "implemented",
            "reduced",
            "improved",
            "launched",
            "coordinated",
            "prepared",
            "negotiated",
        )
        return any(marker in lowered for marker in markers) or any(
            verb.casefold() in lowered for verb in CONTRIBUTION_ACTION_VERBS
        )

    def _dedupe_contribution_signals(
        self,
        signals: list[NormalizedContributionSignal],
    ) -> list[NormalizedContributionSignal]:
        result: list[NormalizedContributionSignal] = []
        seen: set[str] = set()
        for signal in signals:
            key = signal.title.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(signal)
        return result

    def _clean_lines(self, text: str) -> list[str]:
        cleaned_lines: list[str] = []
        for raw_line in text.splitlines():
            line = ZERO_WIDTH_RE.sub("", raw_line).strip()
            if line:
                cleaned_lines.append(line)
        return cleaned_lines

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

            if self._looks_like_hard_achievement_stop(line):
                if current:
                    blocks.append(current)
                    current = []
                break

            if current:
                # Company line внутри нумерованного списка — это, как правило,
                # организация-работодатель текущего пункта (стажировки/проекта
                # в скобках), а не граница раздела «ОПЫТ РАБОТЫ». Организация
                # остаётся в source_text и отрезается от title (_strip_inline_company_tail);
                # но главное — мы НЕ прерываем цикл, иначе пункт 1 обрубил бы
                # пункты 2 и 3 списка.
                if self._looks_like_company_line(line):
                    current.append(line)
                    blocks.append(current)
                    current = []
                    continue
                current.append(line)

        if current:
            blocks.append(current)

        return blocks

    def _trim_lines_after_company_boundary(self, lines: list[str]) -> list[str]:
        result: list[str] = []
        seen_contribution = False

        for line in lines:
            if seen_contribution and self._looks_like_company_line(line):
                break

            result.append(line)
            if self._line_has_contribution_signal(line):
                seen_contribution = True

        return result

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

    def _recover_private_noisy_ai_achievement_title_legacy(self, lines: list[str]) -> str | None:
        return self.legacy_recovery_service.recover_noisy_ai_achievement_title(lines)

    def _looks_like_layout_heading(self, line: str) -> bool:
        normalized = self._normalize(line)
        return normalized in {
            "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ",
            "ЖЕЛАЕМАЯ ДОЛЖНОСТЬ",
            "ОПЫТ РАБОТЫ",
            "ОБРАЗОВАНИЕ",
            "НАВЫКИ",
            "КОНТАКТЫ",
            "ОБЯЗАННОСТИ",
        }

    def _looks_like_resume_layout_noise(self, line: str) -> bool:
        if self.legacy_recovery_service.looks_like_legacy_resume_layout_noise(line):
            return True

        return bool(re.fullmatch(r"[•\s\d]+", line.strip()))

    def _looks_like_hard_achievement_stop(self, line: str) -> bool:
        normalized = self._normalize(line)

        hard_stop_markers = {
            "НАВЫКИ",
            "ОБРАЗОВАНИЕ",
            "ОПЫТ РАБОТЫ",
            "КОНТАКТЫ",
            "КУРСЫ",
            "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ",
            "ПРОМПТ-ИНЖИНИРИНГ УНИВЕРСИТЕТ",
        }

        if normalized in hard_stop_markers:
            return True

        if normalized.startswith(("НАВЫКИ ", "ОБРАЗОВАНИЕ ", "ОПЫТ РАБОТЫ ", "КОНТАКТЫ ", "КУРСЫ ")):
            return True

        if normalized.startswith("ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ"):
            return True

        return False

    def _looks_like_company_line(self, line: str) -> bool:
        cleaned = re.sub(r"\s+", " ", str(line or "")).strip(" .;-–—•")
        if not cleaned:
            return False

        if self._line_has_contribution_signal(cleaned):
            return False

        legal_form_pattern = (
            r"(?:ООО|ОАО|АО|ЗАО|ПАО|ИП|МУП|ГУП|ФГБУ|ГБУ|"
            r"МКУ|МБУ|НКО|АНО|LLC|LTD|INC|CORP)\b"
        )
        if re.match(rf"^{legal_form_pattern}", cleaned, flags=re.IGNORECASE):
            return True

        if re.search(r"[«\"].{2,80}[»\"]", cleaned) and len(cleaned.split()) <= 6:
            return True

        return False

    def _is_numbered_item(self, line: str) -> bool:
        return bool(NUMBERED_ITEM_RE.match(line))

    def _strip_numbering(self, line: str) -> str:
        return NUMBERED_ITEM_RE.sub("", line).strip()

    def _normalize(self, line: str) -> str:
        return re.sub(r"\s+", " ", line.strip()).upper()

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = re.sub(r"\s+", " ", str(value).strip())
            normalized = cleaned.casefold()
            if not cleaned or normalized in seen:
                continue
            seen.add(normalized)
            result.append(cleaned)
        return result
