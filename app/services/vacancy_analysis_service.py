# app\services\vacancy_analysis_service.py

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


SKILL_PATTERNS: dict[str, list[str]] = {
    "Python": [r"\bpython\b"],
    "SQL": [r"\bsql\b"],
    "Git": [r"\bgit\b"],
    "API": [r"\bapi\b"],
    "FastAPI": [r"\bfastapi\b"],
    "PostgreSQL": [r"\bpostgres(?:ql)?\b"],
    "Redis": [r"\bredis\b"],
    "Docker": [r"\bdocker\b"],
    "LLM": [r"\bllm\b", r"large language model", r"языков(?:ая|ые)\s+модел"],
    "Prompt Engineering": [r"prompt engineering", r"промптинг"],
    "Data Science": [r"data science", r"data scientist"],
    "Machine Learning": [r"machine learning", r"машинн(?:ое|ого)\s+обуч"],
    "TensorFlow": [r"\btensorflow\b"],
    "PyTorch": [r"\bpytorch\b"],
    "Pandas": [r"\bpandas\b"],
    "NumPy": [r"\bnumpy\b"],
    "Scikit-learn": [r"scikit-learn", r"sklearn"],
    "NLP": [r"\bnlp\b", r"обработк[аи]\s+текста"],
    "RAG": [r"\brag\b"],
}


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
            start_headings={
                "ТРЕБОВАНИЯ",
                "МЫ ОЖИДАЕМ",
                "ЧТО МЫ ЖДЕМ",
                "ЧТО МЫ ЖДЁМ",
                "ОТ ВАС",
                "REQUIREMENTS",
            },
            stop_headings=self._all_stop_headings(),
        )

        nice_to_have = self._extract_section_items(
            lines,
            start_headings={
                "БУДЕТ ПЛЮСОМ",
                "ПРЕИМУЩЕСТВОМ БУДЕТ",
                "NICE TO HAVE",
                "PLUS",
            },
            stop_headings=self._all_stop_headings(),
        )

        if not must_have:
            must_have = self._fallback_requirement_candidates(lines)

        keywords = self._extract_keywords(vacancy.title, vacancy.description_raw)

        profile = await self.candidate_profile_repository.get_with_related_by_user_id(
            session,
            vacancy.user_id,
        )
        strengths, gaps, match_score = self._compare_with_profile(profile, keywords)

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

    def _compare_with_profile(self, profile, keywords: list[str]) -> tuple[list[dict], list[dict], int | None]:
        if profile is None:
            return [], [{"keyword": k, "reason": "profile_not_found"} for k in keywords], None

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
            if ach.result:
                corpus_parts.append(ach.result)

        profile_corpus = "\n".join(corpus_parts).lower()

        strengths: list[dict] = []
        gaps: list[dict] = []

        for keyword in keywords:
            if keyword.lower() in profile_corpus:
                strengths.append({"keyword": keyword, "evidence": "profile_overlap"})
            else:
                gaps.append({"keyword": keyword, "reason": "not_found_in_profile_text"})

        if not keywords:
            return strengths, gaps, None

        matched = len(strengths)
        match_score = round((matched / len(keywords)) * 100)
        return strengths, gaps, match_score

    def _extract_keywords(self, title: str, description: str) -> list[str]:
        haystack = f"{title}\n{description}".lower()
        found: list[str] = []

        for label, patterns in SKILL_PATTERNS.items():
            if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in patterns):
                found.append(label)

        return found

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
            lowered = cleaned.lower()

            if not cleaned:
                continue

            if any(skill.lower() in lowered for skill in SKILL_PATTERNS.keys()):
                candidates.append(cleaned)

            if len(candidates) >= 8:
                break

        return self._dedupe_preserve_order(candidates)

    def _clean_lines(self, text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _clean_bullet(self, line: str) -> str:
        cleaned = re.sub(r"^[•\-\*\u2022]+\s*", "", line).strip()
        cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned).strip()
        return cleaned

    def _normalize_heading(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.strip()).upper()

    def _all_stop_headings(self) -> set[str]:
        return {
            "ТРЕБОВАНИЯ",
            "ОБЯЗАННОСТИ",
            "ЧЕМ ПРЕДСТОИТ ЗАНИМАТЬСЯ",
            "ЗАДАЧИ",
            "МЫ ПРЕДЛАГАЕМ",
            "УСЛОВИЯ",
            "БУДЕТ ПЛЮСОМ",
            "ПРЕИМУЩЕСТВОМ БУДЕТ",
            "О КОМПАНИИ",
            "REQUIREMENTS",
            "RESPONSIBILITIES",
            "NICE TO HAVE",
            "WE OFFER",
        }

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
