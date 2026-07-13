# app\services\case_prep_service.py

"""Подготовка к кейсам / work sample / тестовым (Этап 9.E).

Детерминированный, explainable on-demand набор practice-кейсов по вакансии.
Переиспользует ТОЛЬКО ``VacancyFitService.build_vacancy_fit`` (ownership 404,
requirements, gaps, supporting_evidence). **Без AI**, без миграции БД, без
персистентности (прогресс/рубрикация ответов — 9.F).

Образец DI + ``_safe_call`` — ``app/services/career_strategy_service.py``;
``_safe_call`` здесь **пробрасывает 404** (ownership) и даёт fallback только
для 400 (analysis/profile missing) → пустой отчёт с ``meta.reason``.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.case_prep import (
    CasePrepReport,
    CaseProvenance,
    PracticeCase,
    build_case,
    build_meta,
    select_case_types,
)
from app.domain.interview_prep import has_leadership_tokens
from app.services.vacancy_fit_service import VacancyFitService


logger = logging.getLogger(__name__)


_HUMAN_REVIEW_NOTE = (
    "deterministic; scenario is a template — adapt to the actual prompt"
)
_NO_FABRICATED_NOTE = "no fabricated specifics (companies, numbers, names)"
_FIT_UNAVAILABLE_NOTE = (
    "vacancy fit unavailable; run vacancy analysis and profile extraction first"
)
_NO_CONFIRMED_EVIDENCE_NOTE = (
    "no confirmed evidence matched this requirement"
)

_RECOMMENDED_FACT_STATUSES = ("confirmed", "user_provided")
_SOURCE_TYPE = "evidence_snippet"
_MATCH_TYPE = "semantic"

_TECHNICAL_CASE_TYPES = ("system_design", "debugging_scenario", "data_analysis")


class CasePrepService:
    """Строит ``CasePrepReport`` practice-кейсов по вакансии."""

    def __init__(self, *, vacancy_fit_service: VacancyFitService | None = None) -> None:
        self.vacancy_fit_service = vacancy_fit_service or VacancyFitService()

    async def build_case_set(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
    ) -> dict[str, Any]:
        fit = await self._safe_call(
            component="vacancy_fit",
            fallback=None,
            call=self.vacancy_fit_service.build_vacancy_fit(
                session,
                vacancy_id=vacancy_id,
                user_id=user_id,
            ),
        )

        if fit is None:
            report = CasePrepReport(
                vacancy_id=vacancy_id,
                cases=[],
                meta={"total": 0, "reason": "vacancy_analysis_or_profile_missing"},
                provenance=CaseProvenance(
                    sources=[],
                    requires_human_review=True,
                    notes=[_FIT_UNAVAILABLE_NOTE],
                ),
            )
            return report.as_dict()

        requirements = list(fit.get("requirements") or [])
        gaps = list((fit.get("evidence_coverage") or {}).get("missing") or [])
        case_types = select_case_types(requirements, gaps)

        cases: list[PracticeCase] = []
        for case_type in case_types:
            anchor, gap_anchor = self._pick_anchor(case_type, requirements, gaps)
            recommended_evidence = self._select_recommended_evidence(anchor)
            cases.append(
                build_case(
                    case_type,
                    requirement=anchor,
                    gap=gap_anchor,
                    recommended_evidence=recommended_evidence,
                )
            )

        meta = build_meta(case_types, requirements)

        notes = [_HUMAN_REVIEW_NOTE, _NO_FABRICATED_NOTE]
        if any(not c.recommended_evidence for c in cases):
            notes.append(_NO_CONFIRMED_EVIDENCE_NOTE)

        provenance = CaseProvenance(
            sources=["vacancy_fit"],
            requires_human_review=True,
            notes=notes,
        )

        report = CasePrepReport(
            vacancy_id=vacancy_id,
            cases=cases,
            meta=meta,
            provenance=provenance,
        )
        return report.as_dict()

    def _pick_anchor(
        self,
        case_type: str,
        requirements: list[dict[str, Any]],
        gaps: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Подобрать якорь (requirement/gap) для типа кейса.

        Technical-типы и behavioral_case — якорь-requirement (с supporting_evidence);
        take_home_brief — якорь-gap (critical), без evidence.
        """
        if case_type == "take_home_brief":
            critical_gap = next(
                (g for g in gaps if str(g.get("severity") or "").lower() == "critical"),
                None,
            )
            if critical_gap is not None:
                return None, critical_gap
            critical_req = next(
                (r for r in requirements if str(r.get("severity") or "").lower() == "critical"),
                None,
            )
            return critical_req, next(
                (g for g in gaps if str(g.get("requirement") or "") == str((critical_req or {}).get("requirement") or "")),
                None,
            )

        # behavioral_case предпочитает leadership-requirement.
        if case_type == "behavioral_case":
            leadership = next(
                (
                    r
                    for r in requirements
                    if has_leadership_tokens(str(r.get("requirement") or "").casefold())
                ),
                None,
            )
            if leadership is not None:
                return leadership, None

        if case_type in _TECHNICAL_CASE_TYPES:
            must_have = next(
                (
                    r
                    for r in requirements
                    if str(r.get("scope") or "") == "must_have"
                    and str(r.get("severity") or "").lower() in {"critical", "important"}
                ),
                None,
            )
            if must_have is not None:
                return must_have, None

        first_req = next(iter(requirements), None)
        return first_req, None

    def _select_recommended_evidence(
        self,
        anchor: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Из supporting_evidence якоря — fact_status ∈ {confirmed, user_provided}, top-2.

        Переиспользует матчинг, уже сделанный в ``VacancyFitService`` (без
        повторного обращения к EvidenceBank/SemanticMatcher — нет side-effect
        записи в БД). Формат — как ``RecommendedEvidenceResponse``.
        """
        if not anchor:
            return []
        supporting = anchor.get("supporting_evidence") or []
        confirmed = [
            m
            for m in supporting
            if str(m.get("fact_status") or "").strip().lower() in _RECOMMENDED_FACT_STATUSES
        ]
        # supporting_evidence уже отсортирован в VacancyFitService по score/strength.
        top = confirmed[:2]
        return [self._to_recommended_evidence(m) for m in top]

    def _to_recommended_evidence(self, match: dict[str, Any]) -> dict[str, Any]:
        score = match.get("score")
        return {
            "achievement_id": match.get("evidence_id"),
            "title": match.get("title") or "",
            "score": float(score) if score is not None else None,
            "reason": match.get("reason") or "",
            "source_type": _SOURCE_TYPE,
            "fact_status": match.get("fact_status") or "",
            "skills": [],
            "match_confidence": self._match_confidence(score),
            "match_type": _MATCH_TYPE,
        }

    @staticmethod
    def _match_confidence(score: Any) -> str:
        try:
            value = float(score)
        except (TypeError, ValueError):
            return "low"
        if value >= 80:
            return "high"
        if value >= 55:
            return "medium"
        return "low"

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
            # 404 — ownership (чужая/несуществующая вакансия): пробрасываем.
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                raise
            logger.warning(
                "case_prep_component_unavailable",
                extra={
                    "component": component,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                },
            )
            return fallback