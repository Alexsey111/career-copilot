# app/services/coverage_mapping_service.py

from __future__ import annotations

import re
from typing import Any

from app.domain.coverage_models import RequirementCoverage
from app.domain.constants import (
    CoverageType,
    EvidenceStrength,
    COVERAGE_STRENGTH_DIRECT_THRESHOLD,
    COVERAGE_STRENGTH_PARTIAL_THRESHOLD,
)


class CoverageMappingService:
    """Сервис для сопоставления требований вакансии с достижениями."""

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in re.findall(r"\w+", text.lower()) if token]

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(CoverageMappingService._tokenize(text))

    @staticmethod
    def _achievement_text(achievement: dict[str, Any]) -> str:
        return " ".join(
            str(achievement.get(field) or "")
            for field in [
                "title",
                "situation",
                "task",
                "action",
                "result",
                "metric_text",
            ]
        )

    def _coverage_score(self, requirement_text: str, achievement_text: str) -> float:
        requirement_tokens = set(self._tokenize(requirement_text))
        achievement_tokens = set(self._tokenize(achievement_text))
        if not requirement_tokens or not achievement_tokens:
            return 0.0

        matches = requirement_tokens & achievement_tokens
        return float(len(matches)) / len(requirement_tokens)

    def _coverage_type(
        self,
        strength: float,
        keyword: str | None,
        achievement_text: str,
    ) -> CoverageType | str:
        keyword_lower = (keyword or "").lower().strip()
        if keyword_lower and keyword_lower in achievement_text.lower():
            return CoverageType.DIRECT
        if strength >= COVERAGE_STRENGTH_DIRECT_THRESHOLD:
            return CoverageType.DIRECT
        if strength >= COVERAGE_STRENGTH_PARTIAL_THRESHOLD:
            return CoverageType.PARTIAL
        if strength > 0.0:
            return CoverageType.INFERRED
        return CoverageType.UNSUPPORTED

    def _evidence_strength(
        self,
        matched_achievement_ids: list[str],
        evidence_items: list[str],
    ) -> EvidenceStrength | str:
        """Определяет силу доказательств на основе fact_status и наличия evidence_note."""
        if not matched_achievement_ids:
            return EvidenceStrength.MISSING
        has_evidence = bool(evidence_items)
        if has_evidence:
            return EvidenceStrength.STRONG
        return EvidenceStrength.MODERATE

    def build_requirement_coverage(
        self,
        achievements: list[dict[str, Any]],
        requirements: list[dict[str, Any]],
    ) -> list[RequirementCoverage]:
        """Строит покрытие требований вакансии достижениями."""
        result: list[RequirementCoverage] = []

        confirmed_achievements = [
            achievement
            for achievement in achievements
            if str(achievement.get("fact_status") or "") == "confirmed"
        ]

        for requirement in requirements:
            requirement_text = str(requirement.get("text") or "").strip()
            keyword = requirement.get("keyword")
            if keyword is not None:
                keyword = str(keyword).strip()

            coverage = RequirementCoverage(
                requirement_text=requirement_text,
                keyword=keyword,
            )

            best_strength = 0.0
            coverage_ids: list[str] = []
            evidence_items: list[str] = []

            for achievement in confirmed_achievements:
                achievement_text = self._achievement_text(achievement)
                strength = self._coverage_score(requirement_text, achievement_text)
                if strength <= 0.0:
                    continue

                if strength > best_strength:
                    best_strength = strength
                if achievement.get("id"):
                    coverage_ids.append(str(achievement["id"]))
                evidence_note = (achievement.get("evidence_note") or "").strip()
                if evidence_note:
                    evidence_items.append(evidence_note)

            coverage.coverage_strength = round(best_strength, 3)
            coverage.matched_achievement_ids = sorted(set(coverage_ids))
            coverage.coverage_type = self._coverage_type(
                strength=coverage.coverage_strength,
                keyword=coverage.keyword,
                achievement_text=" ".join(
                    self._achievement_text(achievement)
                    for achievement in confirmed_achievements
                ),
            )
            coverage.evidence_strength = self._evidence_strength(
                matched_achievement_ids=coverage.matched_achievement_ids,
                evidence_items=evidence_items,
            )
            coverage.evidence_summary = (
                "; ".join(sorted(set(evidence_items)))
                if evidence_items
                else None
            )

            result.append(coverage)

        return result
