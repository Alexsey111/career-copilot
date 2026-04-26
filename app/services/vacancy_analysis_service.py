# app\services\vacancy_analysis_service.py

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


SKILL_PATTERNS: dict[str, list[str]] = {
    "Python": [r"\bpython\b", r"\bпитон\b"],
    "SQL": [r"\bsql\b", r"\bсубд\b", r"баз[аы]\s+данных"],
    "Git": [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"],
    "API": [r"\bapi\b", r"\brest\b", r"rest\s*api", r"интеграц\w*\s+с\s+api"],
    "FastAPI": [r"\bfastapi\b", r"fast\s*api"],
    "PostgreSQL": [r"\bpostgres(?:ql)?\b", r"\bpostgresql\b"],
    "Redis": [r"\bredis\b"],
    "Docker": [r"\bdocker\b", r"\bконтейнеризац"],
    "SQLAlchemy": [r"\bsqlalchemy\b", r"sql\s*alchemy"],
    "Alembic": [r"\balembic\b"],
    "Pydantic": [r"\bpydantic\b"],
    "Pytest": [r"\bpytest\b", r"\bunit\s+tests?\b", r"\bтестировани[ея]\b"],
    "Celery": [r"\bcelery\b"],
    "AsyncIO": [r"\basyncio\b", r"\basync\b", r"асинхрон"],
    "LLM": [r"\bllm\b", r"large language model", r"языков(?:ая|ые)\s+модел"],
    "Prompt Engineering": [r"prompt engineering", r"prompting", r"промптинг", r"промпт-инж"],
    "Data Science": [r"data science", r"data scientist", r"анализ\s+данных"],
    "Machine Learning": [r"machine learning", r"\bml\b", r"машинн(?:ое|ого)\s+обуч"],
    "TensorFlow": [r"\btensorflow\b"],
    "PyTorch": [r"\bpytorch\b"],
    "Pandas": [r"\bpandas\b"],
    "NumPy": [r"\bnumpy\b"],
    "Scikit-learn": [r"scikit-learn", r"sklearn"],
    "NLP": [r"\bnlp\b", r"обработк[аи]\s+текста"],
    "RAG": [r"\brag\b", r"retrieval[-\s]?augmented"],
}


PROFILE_SKILL_SATISFIERS: dict[str, list[str]] = {
    # If a candidate has these more specific skills, they can satisfy generic requirements.
    "SQL": ["PostgreSQL"],
    "API": ["FastAPI"],
}


REQUIREMENT_START_HEADINGS = {
    "ТРЕБОВАНИЯ",
    "ТРЕБУЕМЫЕ НАВЫКИ",
    "КЛЮЧЕВЫЕ НАВЫКИ",
    "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ",
    "МЫ ОЖИДАЕМ",
    "НАШИ ОЖИДАНИЯ",
    "ЧТО МЫ ЖДЕМ",
    "ЧТО МЫ ЖДЁМ",
    "ОТ ВАС",
    "ВАМ ПРЕДСТОИТ",
    "НЕОБХОДИМО",
    "ЧТО НУЖНО",
    "REQUIREMENTS",
    "QUALIFICATIONS",
    "SKILLS",
    "MUST HAVE",
}

NICE_TO_HAVE_START_HEADINGS = {
    "БУДЕТ ПЛЮСОМ",
    "БУДЕТ ПРЕИМУЩЕСТВОМ",
    "ПРЕИМУЩЕСТВОМ БУДЕТ",
    "ЖЕЛАТЕЛЬНО",
    "ДОПОЛНИТЕЛЬНО",
    "NICE TO HAVE",
    "PLUS",
    "OPTIONAL",
}

STOP_HEADINGS = {
    "ТРЕБОВАНИЯ",
    "ТРЕБУЕМЫЕ НАВЫКИ",
    "КЛЮЧЕВЫЕ НАВЫКИ",
    "ПРОФЕССИОНАЛЬНЫЕ НАВЫКИ",
    "ОБЯЗАННОСТИ",
    "ЧЕМ ПРЕДСТОИТ ЗАНИМАТЬСЯ",
    "ЗАДАЧИ",
    "МЫ ПРЕДЛАГАЕМ",
    "УСЛОВИЯ",
    "БУДЕТ ПЛЮСОМ",
    "БУДЕТ ПРЕИМУЩЕСТВОМ",
    "ПРЕИМУЩЕСТВОМ БУДЕТ",
    "ЖЕЛАТЕЛЬНО",
    "О КОМПАНИИ",
    "REQUIREMENTS",
    "RESPONSIBILITIES",
    "NICE TO HAVE",
    "MUST HAVE",
    "QUALIFICATIONS",
    "SKILLS",
    "WE OFFER",
    "BENEFITS",
}


@dataclass(frozen=True)
class RequirementKeyword:
    keyword: str
    scope: str
    requirement_text: str | None
    weight: int


class VacancyAnalysisService:
    def __init__(
        self,
        vacancy_repository: VacancyRepository | None = None,
        vacancy_analysis_repository: VacancyAnalysisRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
    ) -> None:
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.vacancy_analysis_repository = (
            vacancy_analysis_repository or VacancyAnalysisRepository()
        )
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )

    async def analyze_vacancy(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        user_id: UUID,
    ):
        vacancy = await self.vacancy_repository.get_by_id(session, vacancy_id)
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        if vacancy.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        lines = self._clean_lines(vacancy.description_raw)

        must_have = self._extract_section_items(
            lines,
            start_headings=REQUIREMENT_START_HEADINGS,
            stop_headings=STOP_HEADINGS,
        )

        nice_to_have = self._extract_section_items(
            lines,
            start_headings=NICE_TO_HAVE_START_HEADINGS,
            stop_headings=STOP_HEADINGS,
        )

        if not must_have:
            must_have = self._fallback_requirement_candidates(lines)

        keywords = self._extract_keywords(vacancy.title, vacancy.description_raw)

        profile = await self.candidate_profile_repository.get_with_related_by_user_id(
            session,
            vacancy.user_id,
        )
        strengths, gaps, match_score = self._compare_with_profile(
            profile,
            keywords,
            must_have=must_have,
            nice_to_have=nice_to_have,
        )

        analysis = await self.vacancy_analysis_repository.replace_for_vacancy(
            session,
            vacancy_id=vacancy.id,
            must_have_json=[{"text": item} for item in must_have],
            nice_to_have_json=[{"text": item} for item in nice_to_have],
            keywords_json=keywords,
            gaps_json=gaps,
            strengths_json=strengths,
            match_score=match_score,
            analysis_version="deterministic_v1",
        )

        await session.commit()
        await session.refresh(analysis)
        return analysis

    def _compare_with_profile(
        self,
        profile,
        keywords: list[str],
        *,
        must_have: list[str] | None = None,
        nice_to_have: list[str] | None = None,
    ) -> tuple[list[dict], list[dict], int | None]:
        requirement_keywords = self._build_requirement_keywords(
            keywords=keywords,
            must_have=must_have or [],
            nice_to_have=nice_to_have or [],
        )

        if not requirement_keywords:
            return [], [], None

        if profile is None:
            return (
                [],
                [
                    self._build_gap_item(item, reason="profile_not_found")
                    for item in requirement_keywords
                ],
                None,
            )

        profile_corpus = self._build_profile_corpus(profile)

        strengths: list[dict] = []
        gaps: list[dict] = []
        matched_weight = 0
        total_weight = sum(item.weight for item in requirement_keywords)

        for item in requirement_keywords:
            if self._profile_satisfies_keyword(item.keyword, profile_corpus):
                matched_weight += item.weight
                strengths.append(
                    {
                        "keyword": item.keyword,
                        "scope": item.scope,
                        "requirement_text": item.requirement_text,
                        "weight": item.weight,
                        "evidence": "profile_keyword_or_alias_overlap",
                    }
                )
            else:
                gaps.append(
                    self._build_gap_item(
                        item,
                        reason="not_found_in_profile_text",
                    )
                )

        if total_weight <= 0:
            return strengths, gaps, None

        match_score = round((matched_weight / total_weight) * 100)
        return strengths, gaps, match_score

    def _build_requirement_keywords(
        self,
        *,
        keywords: list[str],
        must_have: list[str],
        nice_to_have: list[str],
    ) -> list[RequirementKeyword]:
        items: list[RequirementKeyword] = []

        for requirement_text in must_have:
            for keyword in self._extract_keywords("", requirement_text):
                items.append(
                    RequirementKeyword(
                        keyword=keyword,
                        scope="must_have",
                        requirement_text=requirement_text,
                        weight=3,
                    )
                )

        for requirement_text in nice_to_have:
            for keyword in self._extract_keywords("", requirement_text):
                items.append(
                    RequirementKeyword(
                        keyword=keyword,
                        scope="nice_to_have",
                        requirement_text=requirement_text,
                        weight=1,
                    )
                )

        if not items:
            for keyword in keywords:
                items.append(
                    RequirementKeyword(
                        keyword=keyword,
                        scope="keyword",
                        requirement_text=None,
                        weight=2,
                    )
                )

        return self._dedupe_requirement_keywords(items)

    def _dedupe_requirement_keywords(
        self,
        items: list[RequirementKeyword],
    ) -> list[RequirementKeyword]:
        seen: set[tuple[str, str]] = set()
        result: list[RequirementKeyword] = []

        for item in items:
            key = (item.keyword.lower(), item.scope)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)

        return result

    def _build_gap_item(self, item: RequirementKeyword, *, reason: str) -> dict:
        return {
            "keyword": item.keyword,
            "scope": item.scope,
            "requirement_text": item.requirement_text,
            "weight": item.weight,
            "reason": reason,
        }

    def _build_profile_corpus(self, profile) -> str:
        corpus_parts: list[str] = []

        if profile.headline:
            corpus_parts.append(profile.headline)
        if profile.summary:
            corpus_parts.append(profile.summary)
        if profile.target_roles_json:
            corpus_parts.extend(profile.target_roles_json)

        for exp in profile.experiences:
            corpus_parts.append(exp.company)
            corpus_parts.append(exp.role)
            if exp.description_raw:
                corpus_parts.append(exp.description_raw)

        for ach in profile.achievements:
            corpus_parts.append(ach.title)
            if ach.action:
                corpus_parts.append(ach.action)
            if ach.result:
                corpus_parts.append(ach.result)
            if ach.metric_text:
                corpus_parts.append(ach.metric_text)

        return "\n".join(corpus_parts)

    def _profile_satisfies_keyword(self, keyword: str, profile_corpus: str) -> bool:
        if self._keyword_present_in_text(keyword, profile_corpus):
            return True

        for satisfier in PROFILE_SKILL_SATISFIERS.get(keyword, []):
            if self._keyword_present_in_text(satisfier, profile_corpus):
                return True

        return False

    def _extract_keywords(self, title: str, description: str) -> list[str]:
        haystack = f"{title}\n{description}"
        found: list[str] = []

        for label in SKILL_PATTERNS:
            if self._keyword_present_in_text(label, haystack):
                found.append(label)

        return found

    def _keyword_present_in_text(self, keyword: str, text: str) -> bool:
        if not text:
            return False

        patterns = SKILL_PATTERNS.get(keyword)
        if not patterns:
            escaped = re.escape(keyword)
            patterns = [rf"(?<!\w){escaped}(?!\w)"]

        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    def _extract_section_items(
        self,
        lines: list[str],
        *,
        start_headings: set[str],
        stop_headings: set[str],
    ) -> list[str]:
        capture = False
        items: list[str] = []

        for line in lines:
            normalized = self._normalize_heading(line)

            if normalized in start_headings:
                capture = True
                continue

            if capture and normalized in stop_headings:
                break

            if capture:
                cleaned = self._clean_bullet(line)
                if cleaned and len(cleaned) >= 3:
                    items.append(cleaned)

        return self._dedupe_preserve_order(items)

    def _fallback_requirement_candidates(self, lines: list[str]) -> list[str]:
        candidates: list[str] = []

        for line in lines:
            cleaned = self._clean_bullet(line)
            if not cleaned:
                continue

            if self._extract_keywords("", cleaned):
                candidates.append(cleaned)

            if len(candidates) >= 8:
                break

        return self._dedupe_preserve_order(candidates)

    def _clean_lines(self, text: str) -> list[str]:
        # Some clients/sources may store literal "\n" sequences instead of real newlines.
        text = text.replace("\\r\\n", "\n").replace("\\n", "\n")

        result: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            result.extend(self._expand_inline_heading_line(line))

        return result

    def _expand_inline_heading_line(self, line: str) -> list[str]:
        cleaned = self._clean_bullet(line)

        if ":" not in cleaned and "：" not in cleaned:
            return [line]

        heading_raw, tail = re.split(r"[:：]", cleaned, maxsplit=1)
        heading = self._normalize_heading(heading_raw)
        tail = tail.strip()

        known_headings = (
            REQUIREMENT_START_HEADINGS
            | NICE_TO_HAVE_START_HEADINGS
            | STOP_HEADINGS
        )

        if heading not in known_headings:
            return [line]

        expanded = [heading_raw.strip()]

        if tail:
            expanded.extend(self._split_inline_requirement_tail(tail))

        return expanded

    def _split_inline_requirement_tail(self, value: str) -> list[str]:
        value = value.strip()
        if not value:
            return []

        # Handles: "Python, FastAPI, PostgreSQL" or "Redis; Docker".
        parts = [
            part.strip()
            for part in re.split(r"[,;]\s*", value)
            if part.strip()
        ]

        if len(parts) >= 2:
            return parts

        return [value]

    def _clean_bullet(self, line: str) -> str:
        cleaned = re.sub(r"^[•\-\*\u2022–—✓✔]+\s*", "", line).strip()
        cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned).strip()
        return cleaned

    def _normalize_heading(self, value: str) -> str:
        cleaned = self._clean_bullet(value)
        cleaned = re.sub(r"[:：]+$", "", cleaned).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.upper()

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for value in values:
            key = value.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(value)

        return result
