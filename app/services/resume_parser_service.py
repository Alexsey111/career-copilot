# app\services\resume_parser_service.py

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import docx2txt
import fitz
from fastapi import HTTPException, status


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

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported file type, only PDF and DOCX are supported",
        )

    def _parse_pdf(self, file_bytes: bytes) -> ParsedResume:
        document = fitz.open(stream=file_bytes, filetype="pdf")
        pages: list[str] = []

        for page in document:
            pages.append(page.get_text())

        text = self._normalize_text("\n".join(pages))
        if not text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="could not extract text from PDF; the file may be scanned or image-based",
            )

        return ParsedResume(
            text=text,
            detected_format="pdf",
            metadata={
                "page_count": len(document),
            },
        )

    def _parse_docx(self, file_bytes: bytes, filename: str) -> ParsedResume:
        suffix = Path(filename).suffix or ".docx"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            text = docx2txt.process(tmp.name)

        text = self._normalize_text(text)
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

    def _normalize_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines()]
        non_empty = [line for line in lines if line]
        return "\n".join(non_empty).strip()