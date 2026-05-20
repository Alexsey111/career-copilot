# app\services\evidence_insights_service.py

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository


class EvidenceInsightsService:
    """Deterministic insights over reusable evidence snippets."""

    OVERUSED_USAGE_THRESHOLD = 3
    STAR_FIELDS = ("situation", "task", "action", "result")
    METRIC_PATTERNS = (
        r"\b\d+(?:\.\d+)?%",
        r"\$\s*\d",
        r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|seconds|min|mins|minutes|hr|hrs|hours|day|days|week|weeks|month|months|user|users|customer|customers|request|requests|ticket|tickets|issue|issues|call|calls)\b",
    )
    METRIC_KEYWORDS = (
        "metric",
        "metrics",
        "kpi",
        "latency",
        "throughput",
        "revenue",
        "cost",
        "conversion",
        "retention",
        "growth",
        "accuracy",
        "error rate",
        "performance",
        "time to",
        "sla",
        "slo",
    )

    def __init__(self, repository: EvidenceSnippetRepository | None = None) -> None:
        self.repository = repository or EvidenceSnippetRepository()

    async def get_evidence_insights(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> dict[str, Any]:
        snippets = await self.repository.list_by_user_id(session, user_id=user_id)

        counts = {
            "weak_evidence_count": 0,
            "missing_metrics_count": 0,
            "missing_star_fields_count": 0,
            "unused_evidence_count": 0,
            "overused_evidence_count": 0,
            "unverified_evidence_count": 0,
        }
        recommendations: list[dict[str, Any]] = []

        for snippet in snippets:
            snippet_dict = self._coerce_snippet(snippet)
            snippet_id = snippet_dict.get("id")
            title = str(snippet_dict.get("title") or "Evidence snippet").strip() or "Evidence snippet"
            strength = str(snippet_dict.get("evidence_strength") or "weak").strip().lower()
            fact_status = str(snippet_dict.get("fact_status") or "unverified").strip().lower()
            usage_count = int(snippet_dict.get("usage_count") or 0)

            star_summary = self._resolve_star_summary(snippet_dict)
            has_metrics = self._has_metrics(snippet_dict)
            is_star_complete = self._is_complete_star(star_summary)

            if strength == "weak":
                counts["weak_evidence_count"] += 1
                recommendations.append(
                    self._build_recommendation(
                        type="weak_evidence",
                        evidence_id=snippet_id,
                        title=title,
                        severity="warning",
                        message="Evidence strength is weak. Review the wording, metrics, or supporting context before reuse.",
                    )
                )

            if not has_metrics:
                counts["missing_metrics_count"] += 1
                recommendations.append(
                    self._build_recommendation(
                        type="missing_metric",
                        evidence_id=snippet_id,
                        title=title,
                        severity="warning",
                        message="No measurable metrics were detected. Add concrete numbers or outcome signals if they exist.",
                    )
                )

            if not is_star_complete:
                counts["missing_star_fields_count"] += 1
                recommendations.append(
                    self._build_recommendation(
                        type="incomplete_star",
                        evidence_id=snippet_id,
                        title=title,
                        severity="warning",
                        message="STAR coverage is incomplete. Fill in the missing Situation, Task, Action, or Result fields.",
                    )
                )

            if usage_count == 0:
                counts["unused_evidence_count"] += 1
                recommendations.append(
                    self._build_recommendation(
                        type="unused_evidence",
                        evidence_id=snippet_id,
                        title=title,
                        severity="info",
                        message="This evidence has not been used yet. Consider it for upcoming resume or interview drafts.",
                    )
                )

            if usage_count >= self.OVERUSED_USAGE_THRESHOLD:
                counts["overused_evidence_count"] += 1
                recommendations.append(
                    self._build_recommendation(
                        type="overused_evidence",
                        evidence_id=snippet_id,
                        title=title,
                        severity="warning",
                        message="This evidence is reused often. Consider rotating in alternative evidence to avoid repetition.",
                    )
                )

            if fact_status != "confirmed":
                counts["unverified_evidence_count"] += 1
                recommendations.append(
                    self._build_recommendation(
                        type="unverified_evidence",
                        evidence_id=snippet_id,
                        title=title,
                        severity="warning",
                        message="This fact is not confirmed yet. Keep it out of strong evidence paths until reviewed.",
                    )
                )

        return {
            **counts,
            "recommendations": recommendations,
        }

    def _coerce_snippet(self, snippet: Any) -> dict[str, Any]:
        if hasattr(snippet, "__dict__") and not isinstance(snippet, Mapping):
            return {
                "id": getattr(snippet, "id", None),
                "title": getattr(snippet, "title", None),
                "snippet_text": getattr(snippet, "snippet_text", None),
                "source_type": getattr(snippet, "source_type", None),
                "skills": getattr(snippet, "skills", None),
                "skills_json": getattr(snippet, "skills_json", None),
                "evidence_strength": getattr(snippet, "evidence_strength", None),
                "fact_status": getattr(snippet, "fact_status", None),
                "usage_count": getattr(snippet, "usage_count", 0),
                "used_in_documents_count": getattr(snippet, "used_in_documents_count", 0),
                "used_in_interviews_count": getattr(snippet, "used_in_interviews_count", 0),
                "star_summary": getattr(snippet, "star_summary", None),
                "star_summary_json": getattr(snippet, "star_summary_json", {}),
            }
        if isinstance(snippet, Mapping):
            return dict(snippet)
        return {
            "id": getattr(snippet, "id", None),
            "title": getattr(snippet, "title", None),
            "snippet_text": getattr(snippet, "snippet_text", None),
            "source_type": getattr(snippet, "source_type", None),
            "skills": getattr(snippet, "skills", None),
            "skills_json": getattr(snippet, "skills_json", None),
            "evidence_strength": getattr(snippet, "evidence_strength", None),
            "fact_status": getattr(snippet, "fact_status", None),
            "usage_count": getattr(snippet, "usage_count", 0),
            "used_in_documents_count": getattr(snippet, "used_in_documents_count", 0),
            "used_in_interviews_count": getattr(snippet, "used_in_interviews_count", 0),
            "star_summary": getattr(snippet, "star_summary", None),
            "star_summary_json": getattr(snippet, "star_summary_json", {}),
        }

    def _resolve_star_summary(self, snippet: Mapping[str, Any]) -> dict[str, Any]:
        star_summary = snippet.get("star_summary") or snippet.get("star_summary_json")
        if isinstance(star_summary, Mapping):
            return dict(star_summary)
        if isinstance(star_summary, dict):
            return dict(star_summary)
        return {}

    def _is_complete_star(self, star_summary: Mapping[str, Any]) -> bool:
        return all(
            str(star_summary.get(field) or "").strip()
            for field in self.STAR_FIELDS
        )

    def _has_metrics(self, snippet: Mapping[str, Any]) -> bool:
        texts = [
            str(snippet.get("title") or ""),
            str(snippet.get("snippet_text") or ""),
        ]
        star_summary = self._resolve_star_summary(snippet)
        texts.extend(
            str(star_summary.get(field) or "")
            for field in self.STAR_FIELDS
        )
        combined = " ".join(texts).lower()

        if any(re.search(pattern, combined) for pattern in self.METRIC_PATTERNS):
            return True
        return any(keyword in combined for keyword in self.METRIC_KEYWORDS)

    def _build_recommendation(
        self,
        *,
        type: str,
        evidence_id: Any,
        title: str,
        severity: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "type": type,
            "evidence_id": evidence_id,
            "title": title,
            "message": message,
            "severity": severity,
        }
