# app\services\vacancy_text_extractors\trafilatura_extractor.py

from __future__ import annotations

from bs4 import BeautifulSoup

try:
    import trafilatura
except ModuleNotFoundError:  # pragma: no cover - local/dev environments without the dependency
    trafilatura = None

from app.services.vacancy_text_extractors.base import (
    BaseVacancyExtractor,
)
from app.services.vacancy_text_extractors.contracts import (
    VacancyExtractionResult,
)


class TrafilaturaVacancyExtractor(BaseVacancyExtractor):
    _NOISE_PHRASES = (
        "cookie",
        "cookies",
        "privacy policy",
        "политика конфиденциальности",
        "terms",
        "условия использования",
        "accept cookies",
        "принять все cookie",
        "home",
        "jobs",
        "messaging",
        "notifications",
        "about",
        "careers",
        "blog",
        "contact",
        "главная",
        "вакансии",
        "компании",
        "помощь",
        "privacy",
    )

    async def extract(
        self,
        *,
        url: str,
        html: str,
    ) -> VacancyExtractionResult:
        extracted = None
        method = "fallback_dom"

        if trafilatura is not None:
            extracted = trafilatura.extract(
                html,
                include_links=False,
                include_images=False,
                favor_precision=True,
            )
            if extracted:
                method = "trafilatura"

        if not extracted:
            extracted = self._fallback_extract(html)

        title = self._extract_title(html)
        cleaned = self._cleanup_text(extracted)

        return VacancyExtractionResult(
            title=title,
            text=cleaned,
            extractor="trafilatura",
            extraction_method=method,
            content_length=len(cleaned),
            success=bool(cleaned.strip()),
        )

    def _extract_title(self, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        if soup.title and soup.title.string:
            return soup.title.string.strip()

        return None

    def _fallback_extract(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        return soup.get_text("\n")

    def _cleanup_text(self, text: str) -> str:
        normalized = self._normalize_whitespace(text)
        kept_lines: list[str] = []

        for raw_line in normalized.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            lowered = line.lower()
            if self._is_boilerplate_line(lowered):
                continue

            kept_lines.append(line)

        return self._normalize_whitespace("\n".join(kept_lines))

    def _normalize_whitespace(self, text: str) -> str:
        return "\n".join(line.rstrip() for line in text.splitlines()).strip()

    def _is_boilerplate_line(self, lowered_line: str) -> bool:
        parts = [
            part.strip()
            for part in lowered_line.split("|")
            if part.strip()
        ]

        if parts and all(self._is_noise_token(part) for part in parts):
            return True

        return self._is_noise_token(lowered_line)

    def _is_noise_token(self, value: str) -> bool:
        return any(phrase in value for phrase in self._NOISE_PHRASES)
