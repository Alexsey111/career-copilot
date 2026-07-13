# app\services\career_strategy_service.py

"""Карьерная стратегия для target-track (Этап 9.D).

Детерминированный, explainable отчёт on-demand: ``gap_summary`` (recurring gaps
из ``GapTrendService``, классифицированные на relevant/other относительно
``track.target_roles``), ``learning_plan`` (rule-based шаги reskilling/upskilling
без ссылок на курсы), ``search_tactics`` (rule-based тактика поиска/нетворкинга),
``provenance`` (источники, confidence low/medium нечисловой,
``requires_human_review=True``). Без AI, без миграции БД.

Образец DI + ``_safe_call`` — ``app/services/career_insights_service.py``.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.career_strategy import (
    GapSummaryItem,
    LearningPlan,
    StrategyProvenance,
    StrategyReport,
    SEVERITY_ORDER,
    build_learning_plan_steps,
    build_projected_coverage,
    build_search_tactics,
    classify_gap_relevance,
)
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.services.gap_trend_service import GapTrendService
from app.services.semantic_requirement_matcher import SemanticRequirementMatcher


logger = logging.getLogger(__name__)


_HUMAN_REVIEW_NOTE = (
    "strategy is deterministic and rule-based; no course/price predictions; "
    "review with a human before acting"
)
_GENERIC_TACTICS_NOTE = "target_roles empty — tactics are generic"


class CareerStrategyService:
    """Строит ``StrategyReport`` для target-track из агрегированных gap-трендов."""

    def __init__(
        self,
        gap_trend_service: GapTrendService | None = None,
        profile_repo: CandidateProfileRepository | None = None,
        semantic_matcher: SemanticRequirementMatcher | None = None,
    ) -> None:
        self.gap_trend_service = gap_trend_service or GapTrendService()
        self.profile_repo = profile_repo or CandidateProfileRepository()
        self.semantic_matcher = semantic_matcher or SemanticRequirementMatcher()

    async def build_strategy(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        track_id: UUID,
    ) -> dict[str, Any]:
        profile = await self.profile_repo.get_with_related_by_user_id(session, user_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="target track not found",
            )

        track = next(
            (t for t in (profile.target_tracks or []) if t.id == track_id),
            None,
        )
        if track is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="target track not found",
            )

        gap_trends = await self._safe_call(
            component="gap_trends",
            fallback={"top_recurring_gaps": [], "vacancy_samples": []},
            call=self.gap_trend_service.build_gap_trends(
                session,
                user_id=user_id,
            ),
        )

        top_gaps = gap_trends.get("top_recurring_gaps") or []
        vacancy_samples = gap_trends.get("vacancy_samples") or []

        target_roles = list(track.target_roles_json or [])
        if not target_roles:
            target_roles = list(getattr(profile, "target_roles_json", None) or [])

        gap_summary: list[GapSummaryItem] = []
        for raw in top_gaps[:10]:
            keyword = str(raw.get("keyword") or "").strip()
            if not keyword:
                continue
            is_relevant, reason = classify_gap_relevance(
                keyword,
                list(raw.get("example_vacancy_titles") or []),
                target_roles,
                self.semantic_matcher,
            )
            gap_summary.append(
                GapSummaryItem(
                    keyword=keyword,
                    count=int(raw.get("count") or 0),
                    severity=str(raw.get("severity") or "minor"),
                    example_vacancy_titles=list(raw.get("example_vacancy_titles") or []),
                    is_relevant_to_track=is_relevant,
                    relevance_reason=reason,
                )
            )

        relevant = [g for g in gap_summary if g.is_relevant_to_track]
        steps = build_learning_plan_steps(relevant)
        projected_coverage = build_projected_coverage(steps, gap_summary)
        learning_plan = LearningPlan(steps=steps, projected_coverage=projected_coverage)

        overall_severity = self._overall_severity(gap_summary)
        search_tactics = build_search_tactics(target_roles, overall_severity)

        confidence = "medium" if (gap_summary and vacancy_samples) else "low"
        notes = [_HUMAN_REVIEW_NOTE]
        if not target_roles or not (track.target_roles_json or []):
            notes.append(_GENERIC_TACTICS_NOTE)

        provenance = StrategyProvenance(
            sources=["gap_trend", "target_track"],
            confidence=confidence,
            requires_human_review=True,
            notes=notes,
        )

        report = StrategyReport(
            track_id=track.id,
            gap_summary=gap_summary,
            learning_plan=learning_plan,
            search_tactics=search_tactics,
            provenance=provenance,
        )
        return report.as_dict()

    def _overall_severity(self, gap_summary: list[GapSummaryItem]) -> str | None:
        best: str | None = None
        best_rank = 0
        for g in gap_summary:
            sev = (g.severity or "").strip().lower()
            rank = SEVERITY_ORDER.get(sev, 0)
            if rank > best_rank:
                best_rank = rank
                best = sev
        return best

    async def _safe_call(
        self,
        *,
        component: str,
        fallback: Any,
        call,
    ) -> Any:
        try:
            return await call
        except HTTPException as exc:
            logger.warning(
                "career_strategy_component_unavailable",
                extra={
                    "component": component,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
            return fallback