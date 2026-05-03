# app\services\resume_parser_service.py

from __future__ import annotations

import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import fitz
from fastapi import HTTPException, status

try:
    import docx2txt
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    docx2txt = None


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
        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            pages = [page.get_text() for page in document]
            page_count = len(document)

        text = self._normalize_text("\n".join(pages))
        text = self._repair_common_mojibake(text)

        if not text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="could not extract text from PDF; the file may be scanned or image-based",
            )

        return ParsedResume(
            text=text,
            detected_format="pdf",
            metadata={
                "page_count": page_count,
                "char_length": len(text),
                "line_count": len(text.splitlines()),
            },
        )

    def _parse_docx(self, file_bytes: bytes, filename: str) -> ParsedResume:
        if docx2txt is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="DOCX parsing is unavailable because docx2txt is not installed",
            )

        suffix = Path(filename).suffix or ".docx"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            text = docx2txt.process(tmp.name)

        text = self._normalize_text(text)
        text = self._repair_common_mojibake(text)

        if not text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="could not extract text from DOCX",
            )

        return ParsedResume(
            text=text,
            detected_format="docx",
            metadata={},
        )

    def _parse_txt(self, file_bytes: bytes) -> ParsedResume:
        text, encoding_used = self._decode_text_bytes(file_bytes)
        text = self._normalize_text(text)
        text = self._repair_common_mojibake(text)

        if not text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="could not extract text from TXT",
            )

        return ParsedResume(
            text=text,
            detected_format="txt",
            metadata={
                "encoding": encoding_used,
                "char_length": len(text),
                "line_count": len(text.splitlines()),
            },
        )

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

        return "\n".join(merged_lines).strip()

    def _should_merge_lines(self, prev: str, current: str) -> bool:
        if not prev or not current:
            return False

        prev_lower = prev.lower()
        current_lower = current.lower()

        section_like = {
            "опыт работы",
            "образование",
            "желаемая должность",
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
