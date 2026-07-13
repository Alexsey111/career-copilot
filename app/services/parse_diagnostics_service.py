# app\services\parse_diagnostics_service.py

"""Сервис диагностики парсинга (Этап 8 — ATS-диагностика + anti-hack).

Формирует отчёт «как видит парсер» из уже распарсенного резюме
(``ParsedResume``): распознанные блоки (секции) и их порядок, потерянные
фрагменты (orphan-строки вне секций), структурные предупреждения
(таблицы/колонки/длинные строки/скан-риск/кодировка) и anti-hack находки
скрытого текста + метаданные файла (seed собирает парсер при открытом файле).

См. «первоначальное исследование.md» стр. 16, 18, 39.
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.parse_diagnostics import (
    ExtractedBlock,
    FileMetadata,
    HiddenTextFinding,
    LostBlock,
    ParseDiagnosticsReport,
    StructuralWarning,
)
from app.services.resume_parser_service import ParsedResume


# Эвристический словарь заголовков секций резюме (RU + EN), case-insensitive.
# Ключ — canonical ``kind``, значение — список regex-паттернов заголовков.
_SECTION_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "summary": [
        re.compile(r"^\s*(обо мне|профиль|краткое резюме|summary|objective|profile|about me)\s*:?\s*$", re.I),
    ],
    "experience": [
        re.compile(r"^\s*(опыт работы|опыт|employment|work history|work experience|experience|professional experience)\s*:?\s*$", re.I),
    ],
    "education": [
        re.compile(r"^\s*(образование|education|academic background|academics)\s*:?\s*$", re.I),
    ],
    "skills": [
        re.compile(r"^\s*(навыки|ключевые навыки|компетенции|технологии|skills|key skills|technical skills|competencies|technologies)\s*:?\s*$", re.I),
    ],
    "projects": [
        re.compile(r"^\s*(проекты|проект|projects|personal projects|relevant projects)\s*:?\s*$", re.I),
    ],
    "courses": [
        re.compile(r"^\s*(курсы|сертификаты|курсы и сертификаты|courses|certifications|certificates|training)\s*:?\s*$", re.I),
    ],
    "languages": [
        re.compile(r"^\s*(языки|иностранные языки|languages|language skills)\s*:?\s*$", re.I),
    ],
    "achievements": [
        re.compile(r"^\s*(достижения|ключевые достижения|achievements|key achievements|accomplishments)\s*:?\s*$", re.I),
    ],
}

# Первые строки резюме — контактный блок (email/телефон) — не считаем «потерянным».
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")

_LONG_LINE_THRESHOLD = 180
_WIDE_WHITESPACE_RE = re.compile(r"\s{6,}")
_TABLE_PIPE_RE = re.compile(r"\|.*\|")


class ParseDiagnosticsService:
    """Бесповторный построитель отчёта диагностики — работает из ``ParsedResume``,
    не переоткрывает файл (seed уже собран парсером)."""

    def build_report(self, parsed: ParsedResume) -> ParseDiagnosticsReport:
        text = parsed.text or ""
        lines = text.splitlines()
        seed = (parsed.metadata or {}).get("diagnostics_seed") or {}

        blocks = self._detect_blocks(lines)
        lost = self._detect_lost_blocks(lines, blocks)
        structural = self._detect_structural_warnings(parsed, lines)

        hidden = [HiddenTextFinding(**f) for f in (seed.get("hidden_text") or [])]
        zw = seed.get("zero_width") or {}
        if zw.get("count"):
            hidden.append(
                HiddenTextFinding(
                    kind="zero_width",
                    count=int(zw.get("count", 0)),
                    sample=str(zw.get("sample", ""))[:80],
                    severity="low",
                )
            )

        file_meta_dict = seed.get("file_metadata") or {}
        file_metadata = FileMetadata(
            author=file_meta_dict.get("author"),
            title=file_meta_dict.get("title"),
            producer=file_meta_dict.get("producer"),
            created=file_meta_dict.get("created"),
            creator_tool=file_meta_dict.get("creator_tool"),
        )

        stats = {
            "char_count": len(text),
            "line_count": len(lines),
        }
        # Формат-специфичные метрики (page_count для PDF, encoding для TXT).
        if parsed.detected_format == "pdf" and "page_count" in (parsed.metadata or {}):
            stats["page_count"] = parsed.metadata["page_count"]
        if parsed.detected_format == "txt" and (parsed.metadata or {}).get("encoding"):
            stats["encoding"] = parsed.metadata["encoding"]

        return ParseDiagnosticsReport(
            detected_format=parsed.detected_format,
            stats=stats,
            extracted_blocks=blocks,
            block_order=[b.kind for b in blocks],
            lost_blocks=lost,
            structural_warnings=structural,
            hidden_text_findings=hidden,
            file_metadata=file_metadata,
            metadata_exposure_warning=file_metadata.has_exposure(),
        )

    # --- Block detection -------------------------------------------------

    def _detect_blocks(self, lines: list[str]) -> list[ExtractedBlock]:
        """Эвристически находит секции по заголовкам и разбивает текст на блоки.
        Блок = от заголовка до следующего заголовка. Контактный блок (первые
        строки до первого заголовка) здесь не учитывается — он отдельно в
        ``_detect_lost_blocks`` помечается как контакт, а не «потерянный».
        """
        heading_indexes: list[tuple[int, str, str]] = []  # (line_idx, kind, label)
        for idx, line in enumerate(lines):
            kind, label = self._match_heading(line)
            if kind is not None:
                heading_indexes.append((idx, kind, label))

        blocks: list[ExtractedBlock] = []
        for i, (idx, kind, label) in enumerate(heading_indexes):
            end_idx = heading_indexes[i + 1][0] if i + 1 < len(heading_indexes) else len(lines)
            block_lines = lines[idx + 1 : end_idx]
            block_text = "\n".join(block_lines)
            sample = block_lines[0][:80] if block_lines else ""
            blocks.append(
                ExtractedBlock(
                    kind=kind,
                    label=label,
                    line_start=idx + 1,  # 1-based для удобства чтения
                    line_end=end_idx,
                    char_count=len(block_text),
                    sample=sample,
                )
            )
        return blocks

    def _match_heading(self, line: str) -> tuple[str | None, str]:
        stripped = line.strip()
        if not stripped or len(stripped) > 60:
            # Заголовки секций короткие; длинная строка — не заголовок.
            return None, ""
        for kind, patterns in _SECTION_PATTERNS.items():
            for pat in patterns:
                if pat.match(stripped):
                    return kind, stripped
        return None, ""

    # --- Lost / orphan blocks --------------------------------------------

    def _detect_lost_blocks(self, lines: list[str], blocks: list[ExtractedBlock]) -> list[LostBlock]:
        """Orphan-строки вне распознанных секций. Контактный блок в начале
        (строки до первого заголовка с email/телефоном) не считается потерянным.
        """
        if not blocks:
            # Нет распознанных секций вообще — весь текст «потерян» (кроме коротких контактных).
            return self._orphan_ranges(lines, 0, len(lines), contact_allowed=True)

        lost: list[LostBlock] = []
        first_block_start = blocks[0].line_start - 1  # 0-based индекс строки заголовка

        # Прелюдия до первого заголовка — контактный блок (не lost, если есть email/телефон).
        prelude = lines[:first_block_start]
        prelude_text = "\n".join(prelude).strip()
        has_contacts = bool(_EMAIL_RE.search(prelude_text) or _PHONE_RE.search(prelude_text))
        if prelude and not has_contacts:
            lost.extend(self._orphan_ranges(prelude, 0, len(prelude), contact_allowed=False, reason="text before first section without contacts"))

        # Между блоками и после последнего — orphan-хвосты не ожидаются (блок идёт до след. заголовка),
        # но проверим наличие строк между концом последнего блока и концом документа — это хвост.
        last_block_end = blocks[-1].line_end  # 1-based, exclusive
        if last_block_end < len(lines):
            tail = lines[last_block_end:]
            lost.extend(self._orphan_ranges(tail, last_block_end, len(lines), contact_allowed=False, reason="text after last section"))

        return lost

    def _orphan_ranges(
        self,
        lines_slice: list[str],
        offset: int,
        end: int,
        *,
        contact_allowed: bool,
        reason: str = "not assigned to any recognized section",
    ) -> list[LostBlock]:
        result: list[LostBlock] = []
        chunk: list[str] = []
        chunk_start = 0
        for i, line in enumerate(lines_slice):
            if line.strip():
                if not chunk:
                    chunk_start = i
                chunk.append(line)
            else:
                if chunk:
                    result.append(self._make_lost(chunk, offset + chunk_start, reason))
                    chunk = []
        if chunk:
            result.append(self._make_lost(chunk, offset + chunk_start, reason))
        return result

    def _make_lost(self, chunk: list[str], start_idx: int, reason: str) -> LostBlock:
        sample = " / ".join(c.strip() for c in chunk if c.strip())[:120]
        return LostBlock(
            sample=sample,
            reason=reason,
            line_start=start_idx + 1,  # 1-based
            line_end=start_idx + len(chunk) + 1,
        )

    # --- Structural warnings --------------------------------------------

    def _detect_structural_warnings(self, parsed: ParsedResume, lines: list[str]) -> list[StructuralWarning]:
        warnings: list[StructuralWarning] = []

        long_lines = sum(1 for line in lines if len(line) > _LONG_LINE_THRESHOLD)
        if long_lines:
            warnings.append(
                StructuralWarning(
                    code="long_lines",
                    message=f"{long_lines} строк длиннее {_LONG_LINE_THRESHOLD} символов — ATS-парсер может их обрезать",
                    severity="medium",
                )
            )

        wide_ws = sum(1 for line in lines if _WIDE_WHITESPACE_RE.search(line))
        if wide_ws:
            warnings.append(
                StructuralWarning(
                    code="wide_whitespace_columns",
                    message=f"{wide_ws} строк с широкими пробелами — признак двухколоночной вёрстки, ATS может спутать порядок чтения",
                    severity="high",
                )
            )

        table_like = sum(1 for line in lines if _TABLE_PIPE_RE.search(line))
        if table_like:
            warnings.append(
                StructuralWarning(
                    code="table_like",
                    message=f"{table_like} строк с '|'-разделителями — табличная структура, ATS часто не распознаёт",
                    severity="high",
                )
            )

        if parsed.detected_format == "pdf":
            page_count = (parsed.metadata or {}).get("page_count") or 0
            char_count = len(parsed.text or "")
            if page_count and char_count and char_count / max(page_count, 1) < 200:
                warnings.append(
                    StructuralWarning(
                        code="low_text_density",
                        message=f"мало текста на страницу ({char_count // max(page_count, 1)} символов/стр) — возможно скан/изображение или вёрстка с графикой",
                        severity="medium",
                    )
                )

        encoding = (parsed.metadata or {}).get("encoding")
        if encoding == "utf-8-replace":
            warnings.append(
                StructuralWarning(
                    code="encoding_warning",
                    message="кодировка не определена однозначно, применён fallback с заменой — возможны искажения символов",
                    severity="low",
                )
            )

        return warnings