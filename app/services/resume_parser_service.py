# app\services\resume_parser_service.py

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from fastapi import HTTPException, status

try:
    import docx2txt
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    docx2txt = None

try:
    from docx import Document as _DocxDocument
    from docx.oxml.ns import qn as _docx_qn
    from docx.shared import RGBColor as _DocxRGBColor
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    _DocxDocument = None
    _docx_qn = None
    _DocxRGBColor = None


# Zero-width / invisible Unicode, которые парсер вырезает при нормализации
# (см. ``_normalize_text``). Этап 8: считаем их и показываем пользователю как
# потенциальный вектор stuffing/обхода анти-спам-фильтров, а не удаляем молча.
_ZERO_WIDTH_CHARS = ("​", "‌", "‍", "﻿", "­", "⁠")


@dataclass
class ParsedResume:
    text: str
    detected_format: str
    metadata: dict


class ResumeParserService:
    def parse(
        self,
        *,
        file_bytes: bytes,
        mime_type: str | None,
        filename: str,
    ) -> ParsedResume:
        lower_name = filename.lower()
        mime = (mime_type or "").lower()

        if mime == "application/pdf" or lower_name.endswith(".pdf"):
            return self._parse_pdf(file_bytes)

        if (
            mime
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or lower_name.endswith(".docx")
        ):
            return self._parse_docx(file_bytes, filename)

        if mime == "text/plain" or lower_name.endswith(".txt"):
            return self._parse_txt(file_bytes)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported file type, only PDF, DOCX and TXT are supported",
        )

    def _parse_pdf(self, file_bytes: bytes) -> ParsedResume:
        import fitz

        raw_pages: list[str] = []
        hidden_findings: list[dict] = []
        file_metadata: dict = {}
        page_count = 0

        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            page_count = len(document)
            file_metadata = self._collect_pdf_metadata(document)
            for page in document:
                raw_pages.append(page.get_text())
                self._collect_pdf_hidden_spans(page, hidden_findings)

        raw_text = "\n".join(raw_pages)
        zero_width = self._collect_zero_width(raw_text)

        text = self._normalize_text(raw_text)
        text = self._repair_common_mojibake(text)

        if not text:
            raise HTTPException(
                status_code=422,
                detail="could not extract text from PDF; the file may be scanned or image-based",
            )

        return ParsedResume(
            text=text,
            detected_format="pdf",
            metadata={
                "page_count": page_count,
                "char_length": len(text),
                "line_count": len(text.splitlines()),
                "diagnostics_seed": {
                    "zero_width": zero_width,
                    "hidden_text": hidden_findings,
                    "file_metadata": file_metadata,
                },
            },
        )

    def _collect_pdf_metadata(self, document) -> dict:
        """Этап 8: читаем метаданные PDF (author/producer/creator) — могут
        содержать PII или утечку автора исходного документа."""
        try:
            meta = document.metadata or {}
        except Exception:  # pragma: no cover - defensive
            return {}
        return {
            "author": (meta.get("author") or None),
            "title": (meta.get("title") or None),
            "producer": (meta.get("producer") or None),
            "creator_tool": (meta.get("creator") or None),
            "created": (meta.get("creationDate") or None),
        }

    def _collect_pdf_hidden_spans(self, page, findings: list[dict]) -> None:
        """Этап 8: anti-hack — детект white-on-white и tiny-font в PDF.

        Использует ``page.get_text("dict")`` чтобы получить spans с цветом и
        размером шрифта. White-on-white: span color == 0xFFFFFF (предполагаем
        белый фон — стандарт резюме; severity high, но помечаем как «вероятно
        hidden»). Tiny-font: size < 2pt (severity medium).
        """
        try:
            page_dict = page.get_text("dict")
        except Exception:  # pragma: no cover - defensive
            return

        white_count = 0
        tiny_count = 0
        white_sample = ""
        tiny_sample = ""

        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = (span.get("text") or "").strip()
                    if not span_text:
                        continue
                    color = span.get("color", 0)
                    size = float(span.get("size", 0) or 0)
                    # fitz хранит span color как signed ARGB int (alpha=0xFF для
                    # непрозрачного текста): белый = -1 (0xFFFFFFFF), чёрный =
                    # -16777216 (0xFF000000). Маска низких 24 бит = sRGB.
                    if (color & 0xFFFFFF) == 0xFFFFFF:
                        white_count += 1
                        if not white_sample:
                            white_sample = span_text[:80]
                    if size < 2.0:
                        tiny_count += 1
                        if not tiny_sample:
                            tiny_sample = span_text[:80]

        if white_count:
            findings.append(
                {"kind": "white_on_white", "count": white_count, "sample": white_sample, "severity": "high"}
            )
        if tiny_count:
            findings.append(
                {"kind": "tiny_font", "count": tiny_count, "sample": tiny_sample, "severity": "medium"}
            )

    def _parse_docx(self, file_bytes: bytes, filename: str) -> ParsedResume:
        if docx2txt is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DOCX parsing is unavailable because docx2txt is not installed",
            )

        # docx2txt.process принимает file-like (zipfile.ZipFile) — передаём BytesIO
        # напрямую. NamedTemporaryFile на Windows залочен пока открыт, и docx2txt
        # не мог его переоткрыть (PermissionError); BytesIO работает везде.
        from io import BytesIO

        text = docx2txt.process(BytesIO(file_bytes))

        zero_width = self._collect_zero_width(text)
        file_metadata, hidden_findings = self._collect_docx_metadata_and_hidden(file_bytes)

        text = self._normalize_text(text)
        text = self._repair_common_mojibake(text)

        if not text:
            raise HTTPException(
                status_code=422,
                detail="could not extract text from DOCX",
            )

        return ParsedResume(
            text=text,
            detected_format="docx",
            metadata={
                "diagnostics_seed": {
                    "zero_width": zero_width,
                    "hidden_text": hidden_findings,
                    "file_metadata": file_metadata,
                },
            },
        )

    def _collect_docx_metadata_and_hidden(self, file_bytes: bytes) -> tuple[dict, list[dict]]:
        """Этап 8: читаем core_properties DOCX + детект hidden-text runs.

        Hidden-text в DOCX: ``w:vanish`` (скрытый текст Word), белый цвет шрифта
        (``font.color.rgb == 0xFFFFFF``), tiny-font (<2pt). python-docx даёт
        доступ к runs и XML — docx2txt этого не умеет.
        """
        if _DocxDocument is None:
            return {}, []

        try:
            from io import BytesIO

            doc = _DocxDocument(BytesIO(file_bytes))
        except Exception:  # pragma: no cover - defensive
            return {}, []

        # Метаданные (core_properties) — могут утекать автор/редактор.
        cp = doc.core_properties
        file_metadata = {
            "author": (cp.author or None),
            "title": (cp.title or None),
            "producer": None,
            "creator_tool": (cp.last_modified_by or None),
            "created": (cp.created.isoformat() if cp.created else None),
        }

        vanish_count = 0
        white_count = 0
        tiny_count = 0
        vanish_sample = ""
        white_sample = ""
        tiny_sample = ""

        for paragraph in doc.paragraphs:
            for run in paragraph.runs:
                run_text = (run.text or "").strip()
                if not run_text:
                    continue

                # w:vanish — скрытый текст Word.
                rpr = run._element.rPr
                if rpr is not None and _docx_qn is not None and rpr.findall(_docx_qn("w:vanish")):
                    vanish_count += 1
                    if not vanish_sample:
                        vanish_sample = run_text[:80]

                # Белый цвет шрифта.
                try:
                    color = run.font.color
                    if (
                        color is not None
                        and _DocxRGBColor is not None
                        and color.rgb == _DocxRGBColor(0xFF, 0xFF, 0xFF)
                    ):
                        white_count += 1
                        if not white_sample:
                            white_sample = run_text[:80]
                except Exception:  # pragma: no cover - defensive
                    pass

                # Tiny-font.
                try:
                    size = run.font.size
                    if size is not None and size.pt < 2.0:
                        tiny_count += 1
                        if not tiny_sample:
                            tiny_sample = run_text[:80]
                except Exception:  # pragma: no cover - defensive
                    pass

        findings: list[dict] = []
        if vanish_count:
            findings.append(
                {"kind": "docx_vanish", "count": vanish_count, "sample": vanish_sample, "severity": "high"}
            )
        if white_count:
            findings.append(
                {"kind": "white_on_white", "count": white_count, "sample": white_sample, "severity": "high"}
            )
        if tiny_count:
            findings.append(
                {"kind": "tiny_font", "count": tiny_count, "sample": tiny_sample, "severity": "medium"}
            )

        return file_metadata, findings

    def _parse_txt(self, file_bytes: bytes) -> ParsedResume:
        text, encoding_used = self._decode_text_bytes(file_bytes)
        zero_width = self._collect_zero_width(text)
        text = self._normalize_text(text)
        text = self._repair_common_mojibake(text)

        if not text:
            raise HTTPException(
                status_code=422,
                detail="could not extract text from TXT",
            )

        return ParsedResume(
            text=text,
            detected_format="txt",
            metadata={
                "encoding": encoding_used,
                "char_length": len(text),
                "line_count": len(text.splitlines()),
                "diagnostics_seed": {
                    "zero_width": zero_width,
                    "hidden_text": [],
                    "file_metadata": {},
                },
            },
        )

    def _collect_zero_width(self, text: str) -> dict:
        """Этап 8: считаем zero-width/invisible Unicode (вектор stuffing/обхода
        анти-спам-фильтров) до того, как ``_normalize_text`` их вырежет.

        Возвращает ``{"count": int, "sample": str}`` — sample это фрагмент вокруг
        первого вхождения (до 80 символов), чтобы пользователь видел контекст.
        """
        if not text:
            return {"count": 0, "sample": ""}

        count = 0
        first_pos = -1
        for idx, ch in enumerate(text):
            if ch in _ZERO_WIDTH_CHARS:
                count += 1
                if first_pos < 0:
                    first_pos = idx

        sample = ""
        if first_pos >= 0:
            start = max(0, first_pos - 30)
            end = min(len(text), first_pos + 50)
            sample = text[start:end].strip()[:80]

        return {"count": count, "sample": sample}

    def _decode_text_bytes(self, file_bytes: bytes) -> tuple[str, str]:
        if file_bytes.startswith(b"\xef\xbb\xbf"):
            return file_bytes.decode("utf-8-sig"), "utf-8-sig"

        if file_bytes.startswith(b"\xff\xfe"):
            return file_bytes.decode("utf-16"), "utf-16"

        if file_bytes.startswith(b"\xfe\xff"):
            return file_bytes.decode("utf-16"), "utf-16"

        for encoding in ("utf-8", "cp1251", "cp866", "koi8-r"):
            try:
                return file_bytes.decode(encoding), encoding
            except UnicodeDecodeError:
                continue

        return file_bytes.decode("utf-8", errors="replace"), "utf-8-replace"

    def _repair_common_mojibake(self, text: str) -> str:
        if not text:
            return text

        candidates = [text]

        for source_encoding in ("latin1", "cp1252"):
            try:
                repaired = text.encode(source_encoding).decode("utf-8")
                candidates.append(repaired)
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass

        best = max(candidates, key=self._text_quality_score)
        return best

    def _text_quality_score(self, text: str) -> int:
        cyrillic_count = sum(1 for ch in text if "\u0400" <= ch <= "\u04FF")
        mojibake_markers = text.count("Ð") + text.count("Ñ") + text.count("â")
        return (cyrillic_count * 3) - (mojibake_markers * 2)

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""

        text = unicodedata.normalize("NFKC", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\u00A0", " ")
        text = text.replace("\u200B", "")
        text = text.replace("\u200C", "")
        text = text.replace("\u200D", "")
        text = text.replace("\ufeff", "")
        text = text.replace("\t", " ")

        prepared_lines: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # If a line contains a very wide whitespace gap, it often comes from two columns.
            split_parts = re.split(r"\s{6,}", line)
            for part in split_parts:
                cleaned = re.sub(r"\s+", " ", part).strip()
                if cleaned:
                    prepared_lines.append(cleaned)

        merged_lines: list[str] = []
        for line in prepared_lines:
            if not merged_lines:
                merged_lines.append(line)
                continue

            prev = merged_lines[-1]

            if self._should_merge_lines(prev, line):
                merged_lines[-1] = f"{prev} {line}"
            else:
                merged_lines.append(line)

        text = "\n".join(merged_lines).strip()
        text = self._split_inline_resume_headings(text)
        return text

    def _should_merge_lines(self, prev: str, current: str) -> bool:
        if not prev or not current:
            return False

        prev_lower = prev.lower()
        current_lower = current.lower()

        heading_prefixes = (
            "целевая должность:",
            "целевая позиция:",
            "опыт:",
            "опыт работы:",
            "обязанности:",
            "достижения:",
            "ключевые достижения:",
            "навыки:",
            "ключевые навыки:",
            "профессиональные навыки:",
            "образование:",
            "курсы:",
            "проекты:",
            "стажировки:",
            "контакты:",
            "город:",
        )

        if current_lower.startswith(heading_prefixes):
            return False

        if any(marker in current_lower for marker in heading_prefixes):
            return False

        if any(marker in prev_lower for marker in heading_prefixes) and not prev.endswith(":"):
            return False

        section_like = {
            "опыт работы",
            "образование",
            "целевая должность",
            "целевая позиция",
            "желаемая должность",
            "город",
            "краткое резюме",
            "ключевые навыки",
            "ключевые достижения",
            "профессиональные навыки",
            "навыки",
            "проекты",
            "стажировки",
            "контакты",
            "target role",
            "fit summary",
            "summary",
            "skills",
            "experience",
            "education",
            "projects",
            "review notes",
            "relevant projects",
        }

        if prev_lower in section_like or current_lower in section_like:
            return False

        if self._looks_like_short_target_role_line(prev) and self._looks_like_short_target_role_line(current):
            return False

        if prev.endswith((".", ":", ";", "!", "?")):
            return False

        if re.fullmatch(r"\d+[\.\)]?", prev):
            return False

        if re.match(r"^\d+[\.\)]", current):
            return False

        # Do not merge date/date-range lines with the next block.
        # Example: "1999 - 2001" + "г.Барнаул..." must stay separate.
        if self._looks_like_date_or_period_line(prev):
            return False

        # Do not merge contact/address lines with neighboring content.
        if self._looks_like_contact_or_address_line(prev):
            return False

        if self._looks_like_contact_or_address_line(current):
            return False

        # Do not merge a URL/email/phone line into a descriptive sentence.
        if self._contains_contact_token(prev) or self._contains_contact_token(current):
            return False

        # Merge only short, clearly broken prose lines.
        if len(prev) <= 80 and len(current) <= 80:
            return True

        return False

    def _looks_like_short_target_role_line(self, value: str) -> bool:
        cleaned = re.sub(r"\s+", " ", value.strip(" -–—•"))
        if not cleaned or len(cleaned.split()) > 3:
            return False

        lowered = cleaned.lower()
        role_markers = (
            "сантехник",
            "слесарь",
            "бухгалтер",
            "юрист",
            "врач",
            "инженер",
            "менеджер",
            "developer",
            "engineer",
        )
        return any(marker in lowered for marker in role_markers)

    def _split_inline_resume_headings(self, text: str) -> str:
        headings = (
            "Целевая должность",
            "Целевая позиция",
            "Краткое резюме",
            "Ключевые навыки",
            "Ключевые достижения",
            "Опыт",
            "Опыт работы",
            "Обязанности",
            "Достижения",
            "Навыки",
            "Профессиональные навыки",
            "Образование",
            "Курсы",
            "Проекты",
            "Стажировки",
            "Контакты",
            "Город",
        )

        for heading in sorted(headings, key=len, reverse=True):
            prefix_guard = ""
            suffix_guard = ""
            if heading == "Опыт":
                suffix_guard = r"(?!\s+работы\b)"
            elif heading == "Навыки":
                prefix_guard = r"(?<!ключевые\s)(?<!профессиональные\s)"
            elif heading == "Достижения":
                prefix_guard = r"(?<!ключевые\s)"
            text = re.sub(
                    rf"(?<!^)(?<!\n)\s+{prefix_guard}({re.escape(heading)}){suffix_guard}(?=\s*[:：]|\s+(?-i:[A-ZА-ЯЁ0-9]))",
                r"\n\1",
                text,
                flags=re.IGNORECASE,
            )

        for heading in sorted(headings, key=len, reverse=True):
            prefix_guard = ""
            suffix_guard = ""
            if heading == "Опыт":
                suffix_guard = r"(?!\s+работы\b)"
            elif heading == "Навыки":
                prefix_guard = r"(?<!ключевые\s)(?<!профессиональные\s)"
            elif heading == "Достижения":
                prefix_guard = r"(?<!ключевые\s)"
            text = re.sub(
                rf"(?im)^{prefix_guard}({re.escape(heading)}){suffix_guard}(?=\s*[:：]|\s+(?-i:[A-ZА-ЯЁ0-9]))(?:\s*[:：])?\s+(.+)$",
                r"\1\n\2",
                text,
                flags=re.IGNORECASE,
            )

        return text

    def _looks_like_date_or_period_line(self, value: str) -> bool:
        value = value.strip().lower()

        if re.fullmatch(r"\d{4}\s*[-–—]\s*(\d{4}|по настоящее время|present|now)", value):
            return True

        if re.fullmatch(
            r"\d{2}\.\d{2}\.\d{4}\s*[-–—]\s*(\d{2}\.\d{2}\.\d{4}|по настоящее время|present|now)",
            value,
        ):
            return True

        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value):
            return True

        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}\s+г\.?р\.?", value):
            return True

        return False

    def _contains_contact_token(self, value: str) -> bool:
        lowered = value.lower()

        if "@" in value:
            return True

        if "http://" in lowered or "https://" in lowered or "www." in lowered:
            return True

        if re.search(r"(\+7|8)\s*[\(\- ]?\d{3}", value):
            return True

        return False

    def _looks_like_contact_or_address_line(self, value: str) -> bool:
        lowered = value.strip().lower()

        if self._contains_contact_token(value):
            return True

        address_markers = (
            "г.",
            "г ",
            "город ",
            "ул.",
            "улица ",
            "пр.",
            "проспект ",
            "д.",
            "дом ",
            "кв.",
            "квартира ",
            "россия",
        )

        return any(marker in lowered for marker in address_markers)
