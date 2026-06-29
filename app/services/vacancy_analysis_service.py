# app\services\vacancy_analysis_service.py

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.requirement_normalization import (
    classify_requirement_phrase,
    is_ignored_requirement_header,
    normalize_requirement_phrase,
    normalize_requirement_phrases,
)
from app.domain.skills.utils import (
    extract_keywords,
    get_related_skills,
    keyword_present,
)
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.models.entities import VacancyAnalysis
from app.services.requirement_canonicalizer import (
    canonicalize_requirement,
    canonicalize_requirements,
    split_atomic_requirements,
)
from app.services.semantic_requirement_matcher import SemanticRequirementMatcher


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

SOFT_AI_INTEREST_KEYWORDS = {
    "AI Interaction",
    "AI Workflow",
    "LLM",
}

SOFT_AI_INTEREST_PATTERNS = [
    r"интерес\s+к\s+(?:ai|ии|искусственн\w+\s+интеллект)",
    r"интересоваться\s+(?:ai|ии|искусственн\w+\s+интеллект)",
    r"желани\w+\s+развиваться\s+в\s+(?:ai|ии|искусственн\w+\s+интеллект)",
    r"curiosity\s+(?:about|for)\s+ai",
    r"interest\s+in\s+ai",
]

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
    "ПОСЛЕ ОТКЛИКА",
    "ЭТАПЫ",
    "ЭТАПЫ ОТБОРА",
    "ПРОЦЕСС ОТБОРА",
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

STOP_AFTER_REQUIREMENTS_HEADINGS = {
    "мы предлагаем",
    "условия",
    "о компании",
    "оплата труда",
    "график и условия работы",
    "ключевые навыки",
}

NORMALIZED_STOP_AFTER_REQUIREMENTS_HEADINGS = {
    heading.upper()
    for heading in STOP_AFTER_REQUIREMENTS_HEADINGS
}


@dataclass(frozen=True)
class RequirementKeyword:
    keyword: str
    scope: str
    requirement_text: str | None
    weight: int


from app.schemas.json_contracts import VacancyAnalysisSchema


class VacancyAnalysisService:
    def __init__(
        self,
        vacancy_repository: VacancyRepository | None = None,
        vacancy_analysis_repository: VacancyAnalysisRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
    ) -> None:
        self.vacancy_repo = vacancy_repository or VacancyRepository()
        self.analysis_repo = (
            vacancy_analysis_repository or VacancyAnalysisRepository()
        )
        self.profile_repo = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.semantic_matcher = SemanticRequirementMatcher()

    async def analyze_vacancy(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        user_id: UUID,
    ):
        vacancy = await self.vacancy_repo.get_by_id(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if vacancy is None:
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

        profile = await self.profile_repo.get_with_related_by_user_id(
            session,
            vacancy.user_id,
        )
        strengths, gaps, match_score = self._compare_with_profile(
            profile,
            keywords,
            must_have=must_have,
            nice_to_have=nice_to_have,
        )

        # Валидация JSON-контракта перед сохранением
        validated = VacancyAnalysisSchema(
            must_have=[
                {
                    "text": item,
                    "classification": classify_requirement_phrase(item),
                }
                for item in must_have
            ],
            nice_to_have=[
                {
                    "text": item,
                    "scope": "nice_to_have",
                    "classification": classify_requirement_phrase(item),
                }
                for item in nice_to_have
            ],
            keywords=keywords,
            gaps=gaps,
            strengths=strengths,
            match_score=match_score,
        )

        analysis = await self.analysis_repo.replace_for_vacancy(
            session,
            vacancy_id=vacancy.id,
            must_have_json=[item.model_dump() for item in validated.must_have],
            nice_to_have_json=[item.model_dump() for item in validated.nice_to_have],
            keywords_json=validated.keywords,
            gaps_json=[item.model_dump() for item in validated.gaps],
            strengths_json=[item.model_dump() for item in validated.strengths],
            match_score=validated.match_score,
            analysis_version="deterministic_v1",
        )

        await session.commit()
        return analysis

    async def match_vacancy(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        user_id: UUID,
    ) -> VacancyAnalysis:
        analysis = await self.analysis_repo.get_latest_for_vacancy(
            session,
            vacancy_id,
            user_id=user_id,
        )

        if analysis is None:
            analysis = await self.analyze_vacancy(
                session,
                vacancy_id=vacancy_id,
                user_id=user_id,
            )

        profile = await self.profile_repo.get_with_related_by_user_id(
            session, user_id=user_id
        )

        strengths, gaps, score = self._compare_with_profile_simple(
            keywords=analysis.keywords_json or [],
            profile=profile,
        )

        # Валидация JSON-контракта перед сохранением
        validated = VacancyAnalysisSchema(
            must_have=analysis.must_have_json or [],
            nice_to_have=analysis.nice_to_have_json or [],
            keywords=analysis.keywords_json or [],
            gaps=gaps,
            strengths=strengths,
            match_score=score,
        )

        return await self.analysis_repo.replace_for_vacancy(
            session,
            vacancy_id=vacancy_id,
            must_have_json=[item.model_dump() for item in validated.must_have],
            nice_to_have_json=[item.model_dump() for item in validated.nice_to_have],
            keywords_json=validated.keywords,
            gaps_json=[item.model_dump() for item in validated.gaps],
            strengths_json=[item.model_dump() for item in validated.strengths],
            match_score=validated.match_score,
            analysis_version="deterministic_match_v1",
        )

    def _compare_with_profile_simple(
        self,
        *,
        keywords: list[str],
        profile,
    ) -> tuple[list[dict], list[dict], int | None]:
        if profile is None or not keywords:
            return (
                [],
                [
                    {
                        "keyword": kw,
                        "scope": "must_have",
                        "requirement_text": None,
                        "weight": 1,
                        "reason": "profile_not_found"
                        if profile is None
                        else "no_keywords",
                    }
                    for kw in keywords
                ],
                None,
            )

        profile_corpus = self._build_profile_corpus(profile)

        strengths: list[dict] = []
        gaps: list[dict] = []
        matched = 0

        for keyword in keywords:
            if self._profile_satisfies_keyword(keyword, profile_corpus):
                matched += 1
                strengths.append(
                    {
                        "keyword": keyword,
                        "scope": "must_have",
                        "requirement_text": None,
                        "weight": 1,
                        "evidence": "profile_keyword_or_alias_overlap",
                    }
                )
            else:
                gaps.append(
                    {
                        "keyword": keyword,
                        "scope": "must_have",
                        "requirement_text": None,
                        "weight": 1,
                        "reason": "not_found_in_profile_text",
                    }
                )

        if len(keywords) <= 0:
            return strengths, gaps, None

        score = round((matched / len(keywords)) * 100)
        return strengths, gaps, score

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
        analysis_keywords = keywords

        for requirement_text in must_have:
            requirement_keywords = self._extract_keywords("", requirement_text)
            if not requirement_keywords:
                fallback_keyword = self._compact_requirement_label(requirement_text)
                requirement_keywords = [fallback_keyword] if fallback_keyword else []

            for keyword in requirement_keywords:
                if self._is_soft_ai_interest_keyword(keyword, requirement_text):
                    continue
                items.append(
                    RequirementKeyword(
                        keyword=keyword,
                        scope="must_have",
                        requirement_text=requirement_text,
                        weight=3,
                    )
                )

        for requirement_text in nice_to_have:
            requirement_keywords = self._extract_keywords("", requirement_text)
            if not requirement_keywords:
                fallback_keyword = self._compact_requirement_label(requirement_text)
                requirement_keywords = [fallback_keyword] if fallback_keyword else []

            for keyword in requirement_keywords:
                items.append(
                    RequirementKeyword(
                        keyword=keyword,
                        scope="nice_to_have",
                        requirement_text=requirement_text,
                        weight=1,
                    )
                )

        if not items:
            for keyword in analysis_keywords:
                items.append(
                    RequirementKeyword(
                        keyword=keyword,
                        scope="must_have",
                        requirement_text=None,
                        weight=2,
                    )
                )

        return self._dedupe_requirement_keywords(items)

    def _compact_requirement_label(self, value: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        if not cleaned:
            return None

        cleaned = normalize_requirement_phrase(cleaned)

        if len(cleaned) > 120:
            cleaned = cleaned[:120].rsplit(" ", 1)[0].strip(" .;-–—•")

        return cleaned or None

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
        if keyword_present(keyword, profile_corpus):
            return True

        for satisfier in get_related_skills(keyword):
            if keyword_present(satisfier, profile_corpus):
                return True

        return False

    def _extract_keywords(self, title: str, description: str) -> list[str]:
        haystack = f"{title}\n{description}"
        return extract_keywords(haystack)

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

            if capture and (
                normalized in stop_headings
                or self._is_stop_after_requirements_heading(normalized)
            ):
                break

            if capture:
                cleaned = self._clean_bullet(line)
                items.extend(self._normalize_requirement_items(cleaned))
                if self._has_requirement_stop_tail(cleaned):
                    break

        requirements = self._dedupe_preserve_order(items)
        requirements = [
            child
            for group in (self._split_atomic_requirement(item) for item in requirements)
            for child in group
        ]
        requirements = self._run_semantic_requirement_matcher(requirements)
        return self._dedupe_preserve_order(requirements)

    def _fallback_requirement_candidates(self, lines: list[str]) -> list[str]:
        candidates: list[str] = []

        for line in lines:
            normalized = self._normalize_heading(line)
            if normalized in REQUIREMENT_START_HEADINGS:
                continue
            if normalized in NICE_TO_HAVE_START_HEADINGS or self._is_stop_after_requirements_heading(normalized):
                break

            cleaned = self._clean_bullet(line)
            normalized_items = self._normalize_requirement_items(cleaned)
            if not normalized_items:
                continue

            for normalized_item in normalized_items:
                classification = classify_requirement_phrase(normalized_item)
                if (
                    self._extract_keywords("", normalized_item)
                    or classification != "competency"
                    or "полевой команд" in normalized_item.casefold()
                ):
                    candidates.append(normalized_item)

            if len(candidates) >= 8:
                break
            if self._has_requirement_stop_tail(cleaned):
                break

        requirements = self._dedupe_preserve_order(candidates)
        requirements = [
            child
            for group in (self._split_atomic_requirement(item) for item in requirements)
            for child in group
        ]
        requirements = self._run_semantic_requirement_matcher(requirements)
        return self._dedupe_preserve_order(requirements)

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

        prefix_match = self._match_heading_prefix(cleaned)
        if prefix_match is not None:
            heading_raw, tail = prefix_match
            expanded = [heading_raw]
            if tail:
                expanded.extend(self._split_inline_requirement_tail(tail))
            return expanded

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

    def _split_atomic_requirement(self, value: str) -> list[str]:
        return [
            item.display
            for item in canonicalize_requirements(split_atomic_requirements(value))
        ]

    def _is_bad_atomic_requirement_fragment(self, value: str) -> bool:
        return canonicalize_requirement(value).is_noise

    def _run_semantic_requirement_matcher(self, requirements: list[str]) -> list[str]:
        if not requirements:
            return []

        # Validation-only pass: keeps the downstream pipeline unchanged while
        # reusing the service-level semantic matcher on atomic requirements.
        for requirement in requirements:
            self.semantic_matcher.match(requirement, requirements)

        return requirements

    def _normalize_requirement_items(self, value: str) -> list[str]:
        cleaned = self._strip_requirement_tail(value)
        cleaned = re.sub(r"\s+", " ", str(cleaned or "")).strip(" .;-–—•:")
        if len(cleaned) < 3:
            return []
        if is_ignored_requirement_header(cleaned):
            return []

        normalized_items = normalize_requirement_phrases(cleaned)
        normalized_items = [
            item
            for item in normalized_items
            if item and not is_ignored_requirement_header(item)
        ]

        return normalized_items

    def _strip_requirement_tail(self, value: str) -> str:
        return re.split(
            r"\s+(?:мы предлагаем|условия|о компании|оплата труда|график и условия работы|ключевые навыки)\b",
            str(value or ""),
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip(" .;-–—•")

    def _has_requirement_stop_tail(self, value: str) -> bool:
        return bool(
            re.search(
                r"\s+(?:мы предлагаем|условия|о компании|оплата труда|график и условия работы|ключевые навыки)\b",
                str(value or ""),
                flags=re.IGNORECASE,
            )
        )

    def _is_stop_after_requirements_heading(self, normalized_heading: str) -> bool:
        return any(
            normalized_heading == heading
            or normalized_heading.startswith(f"{heading} ")
            for heading in NORMALIZED_STOP_AFTER_REQUIREMENTS_HEADINGS
        )

    def _match_heading_prefix(self, value: str) -> tuple[str, str] | None:
        known_headings = sorted(
            REQUIREMENT_START_HEADINGS
            | NICE_TO_HAVE_START_HEADINGS
            | STOP_HEADINGS,
            key=len,
            reverse=True,
        )
        normalized_value = self._normalize_heading(value)

        for heading in known_headings:
            if not normalized_value.startswith(f"{heading} "):
                continue

            tail = value[len(heading):].strip(" :-–—")
            if not tail:
                continue
            return heading.title(), tail

        return None

    def _is_soft_ai_interest_keyword(self, keyword: str, requirement_text: str | None) -> bool:
        if keyword not in SOFT_AI_INTEREST_KEYWORDS:
            return False

        text = str(requirement_text or "").casefold()
        if any(tool in text for tool in ["chatgpt", "chat-gpt", "claude", "llm"]):
            return False

        return any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in SOFT_AI_INTEREST_PATTERNS
        )

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
