from __future__ import annotations

from typing import Any

from app.domain.star_models import STARStoryDraft, Competency, CompetencyMapping
from app.services.evidence_quality_service import EvidenceQualityService
from app.domain.constants import (
    CoverageType,
    EvidenceStrength,
    COVERAGE_STRENGTH_DIRECT_THRESHOLD,
    COVERAGE_STRENGTH_PARTIAL_THRESHOLD,
)


class STARExtractionService:
    """Сервис извлечения структурированных STAR-историй из достижений."""

    def __init__(self) -> None:
        self.evidence_service = EvidenceQualityService()

    def extract_star_story(
        self,
        achievement: dict[str, Any],
    ) -> STARStoryDraft:
        """
        Извлекает структурированную STAR-историю из достижения.
        """
        achievement_id = str(achievement.get("id", ""))
        situation = str(achievement.get("situation") or "")
        task = str(achievement.get("task") or "")
        action = str(achievement.get("action") or "")
        result = str(achievement.get("result") or "")

        quality_score = self.evidence_service.calculate_evidence_quality_score(achievement)
        evidence_strength = self._infer_evidence_strength(achievement)

        return STARStoryDraft(
            achievement_id=achievement_id,
            situation=situation,
            task=task,
            action=action,
            result=result,
            evidence_strength=evidence_strength,
            quality_score=quality_score,
        )

    def _infer_evidence_strength(
        self,
        achievement: dict[str, Any],
    ) -> EvidenceStrength | str:
        """Выводит силу доказательств на основе fact_status и evidence_note."""
        fact_status = str(achievement.get("fact_status") or "")
        evidence_note = str(achievement.get("evidence_note") or "").strip()

        if fact_status == "confirmed" and evidence_note:
            return EvidenceStrength.STRONG
        if fact_status == "confirmed" or evidence_note:
            return EvidenceStrength.MODERATE
        if fact_status == "pending":
            return EvidenceStrength.WEAK
        return EvidenceStrength.MISSING

    def extract_all_stars(
        self,
        achievements: list[dict[str, Any]],
    ) -> list[STARStoryDraft]:
        """Извлекает STAR-истории из всех достижений."""
        return [self.extract_star_story(ach) for ach in achievements]

    def map_to_competencies(
        self,
        requirements: list[dict[str, Any]],
        star_stories: list[STARStoryDraft],
        competency_keywords: dict[str, list[str]],
    ) -> list[CompetencyMapping]:
        """
        Маппит требования вакансии на компетенции и STAR истории.

        Args:
            requirements: Список требований из вакансии
            star_stories: Извлечённые STAR-истории
            competency_keywords: Словарь компетенция → ключевые слова

        Returns:
            Список CompetencyMapping объектов
        """
        results: list[CompetencyMapping] = []

        for req in requirements:
            req_text = str(req.get("text") or "")
            req_keyword = req.get("keyword")

            # Определяем компетенцию по ключевому слову
            competency = self._match_competency(req_text, req_keyword, competency_keywords)

            # Ищем matching STAR истории
            matched_story_ids = self._find_matching_stars(
                req_text=req_text,
                req_keyword=req_keyword,
                star_stories=star_stories,
            )

            # Вычисляем coverage
            coverage_strength = self._calculate_coverage_strength(
                req_text=req_text,
                star_stories=star_stories,
                matched_ids=matched_story_ids,
            )

            coverage_type = self._determine_coverage_type(
                coverage_strength=coverage_strength,
                matched_ids=matched_story_ids,
            )

            results.append(CompetencyMapping(
                requirement_text=req_text,
                competency=competency,
                matched_story_ids=matched_story_ids,
                coverage_type=coverage_type,
                coverage_strength=coverage_strength,
            ))

        return results

    def _match_competency(
        self,
        req_text: str,
        req_keyword: str | None,
        competency_keywords: dict[str, list[str]],
    ) -> Competency:
        """Сопоставляет требование с компетенцией."""
        req_lower = req_text.lower()
        keyword_lower = (req_keyword or "").lower()

        for comp_name, keywords in competency_keywords.items():
            for kw in keywords:
                if kw.lower() in req_lower or kw.lower() == keyword_lower:
                    return Competency(
                        name=comp_name,
                        keywords=keywords,
                    )

        # Дефолтная компетенция
        return Competency(
            name="general",
            description=req_text,
            keywords=[keyword_lower] if keyword_lower else [],
        )

    def _find_matching_stars(
        self,
        req_text: str,
        req_keyword: str | None,
        star_stories: list[STARStoryDraft],
    ) -> list[str]:
        """Находит STAR истории, соответствующие требованию."""
        import re

        req_lower = req_text.lower()
        keyword_lower = (req_keyword or "").lower()
        tokens = set(re.findall(r"\w+", req_lower))

        if keyword_lower:
            tokens.add(keyword_lower)

        matched_ids: list[str] = []

        for story in star_stories:
            story_text = f"{story.situation} {story.task} {story.action} {story.result}".lower()
            story_tokens = set(re.findall(r"\w+", story_text))

            # Проверяем совпадение
            if keyword_lower and keyword_lower in story_text:
                matched_ids.append(story.achievement_id)
            elif tokens & story_tokens:
                overlap = len(tokens & story_tokens) / len(tokens)
                if overlap >= 0.3:
                    matched_ids.append(story.achievement_id)

        return matched_ids

    def _calculate_coverage_strength(
        self,
        req_text: str,
        star_stories: list[STARStoryDraft],
        matched_ids: list[str],
    ) -> float:
        """Рассчитывает силу покрытия на основе matching stories."""
        if not matched_ids:
            return 0.0

        matched_stories = [s for s in star_stories if s.achievement_id in matched_ids]

        # Усреднённый quality_score matched историй
        if matched_stories:
            avg_quality = sum(s.quality_score for s in matched_stories) / len(matched_stories)
            return round(avg_quality, 3)

        return 0.0

    def _determine_coverage_type(
        self,
        coverage_strength: float,
        matched_ids: list[str],
    ) -> CoverageType | str:
        """Определяет тип покрытия."""
        if not matched_ids:
            return CoverageType.UNSUPPORTED
        if coverage_strength >= COVERAGE_STRENGTH_DIRECT_THRESHOLD:
            return CoverageType.DIRECT
        if coverage_strength >= COVERAGE_STRENGTH_PARTIAL_THRESHOLD:
            return CoverageType.PARTIAL
        return CoverageType.INFERRED
