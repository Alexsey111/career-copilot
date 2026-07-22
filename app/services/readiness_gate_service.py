# app\services\readiness_gate_service.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ReadinessGateResult:
    ready: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: float | None = None


class ReadinessGateService:
    """Semantic readiness gate for document-level operational decisions."""

    LOW_ATS_THRESHOLD = 0.7

    def evaluate_document_readiness(self, document) -> ReadinessGateResult:
        content = document.content_json or {}
        sections = content.get("sections", {})
        evaluation = content.get("evaluation", {})
        meta = content.get("meta", {})

        blockers: list[str] = []
        warnings: list[str] = []

        if getattr(document, "review_status", None) != "approved":
            blockers.append("document review_status is not approved")

        unresolved_claims = sections.get("claims_needing_confirmation", [])
        if unresolved_claims:
            blockers.append("document has unresolved claims requiring confirmation")

        critical_failures = evaluation.get("critical_failures", [])
        if critical_failures:
            blockers.append("document has unresolved critical evaluation failures")

        if not getattr(document, "is_active", False):
            blockers.append("document is not active")

        coverage_gaps = (
            evaluation.get("coverage_gaps")
            or sections.get("coverage_gaps")
            or sections.get("gap_requirements")
            or []
        )
        if coverage_gaps:
            warnings.append("document has coverage gaps")

        readiness_payload = self._resolve_readiness_payload(content, evaluation, meta)
        score = self._resolve_score(readiness_payload)
        ats_score = self._resolve_ats_score(readiness_payload, evaluation, meta)

        if ats_score is not None and ats_score < self.LOW_ATS_THRESHOLD:
            warnings.append(f"document has low ATS score ({ats_score:.2f})")

        if self._has_missing_metrics(sections):
            warnings.append("document has achievements with missing metrics")

        return ReadinessGateResult(
            ready=len(blockers) == 0,
            blockers=blockers,
            warnings=warnings,
            score=score,
        )

    @staticmethod
    def _resolve_readiness_payload(
        content: dict[str, Any],
        evaluation: dict[str, Any],
        meta: dict[str, Any],
    ) -> dict[str, Any] | float | int | None:
        return (
            content.get("readiness_score")
            or evaluation.get("readiness_score")
            or meta.get("readiness_score")
        )

    @staticmethod
    def _resolve_score(readiness_payload: dict[str, Any] | float | int | None) -> float | None:
        if isinstance(readiness_payload, dict):
            score = readiness_payload.get("overall_score")
            if isinstance(score, (int, float)):
                return float(score)
            return None
        if isinstance(readiness_payload, (int, float)):
            return float(readiness_payload)
        return None

    @staticmethod
    def _resolve_ats_score(
        readiness_payload: dict[str, Any] | float | int | None,
        evaluation: dict[str, Any],
        meta: dict[str, Any],
    ) -> float | None:
        if isinstance(readiness_payload, dict):
            score = readiness_payload.get("ats_score")
            if isinstance(score, (int, float)):
                return float(score)

        for candidate in (evaluation.get("ats_score"), meta.get("ats_score")):
            if isinstance(candidate, (int, float)):
                return float(candidate)
        return None

    @staticmethod
    def _has_missing_metrics(sections: dict[str, Any]) -> bool:
        selected_achievements = sections.get("selected_achievements", [])
        if not isinstance(selected_achievements, list):
            return False

        for achievement in selected_achievements:
            if not isinstance(achievement, dict):
                continue
            metric_text = achievement.get("metric_text")
            if metric_text is None or (isinstance(metric_text, str) and not metric_text.strip()):
                return True
        return False
