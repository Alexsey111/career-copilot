"""ImpactMeasurementService — сервис измерения влияния выполненных рекомендаций."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.impact_measurement import ImpactRecommendationType
from app.domain.readiness_evaluation import ReadinessEvaluation
from app.repositories.impact_measurement_repository import ImpactMeasurementRepository
from app.services.review_action_loop import (
    ReadinessDelta,
    RecommendationExecutionStatus,
    RecommendationImpactMeasurement,
)


class ImpactMeasurementService:
    """
    Сервис для измерения влияния выполненных рекомендаций.

    Ответственность ТОЛЬКО:
    - compute delta between readiness evaluations
    - create impact measurement record
    - track execution timing

    Никаких:
    - document mutation
    - readiness evaluation
    - recommendation execution logic
    """

    def __init__(
        self,
        repository: ImpactMeasurementRepository,
    ) -> None:
        self._repository = repository

    async def measure_impact(
        self,
        session: AsyncSession,
        recommendation_id: str,
        recommendation_type: str,
        target_achievement_id: str | None,
        changes: dict[str, Any],
        before_evaluation: ReadinessEvaluation,
        after_evaluation: ReadinessEvaluation,
        before_snapshot_id: UUID,
        after_snapshot_id: UUID,
        document_id: UUID,
        started_at: datetime,
        completed_at: datetime,
    ) -> RecommendationImpactMeasurement:
        """
        Измеряет влияние выполненной рекомендации и сохраняет в БД.

        Args:
            session: Database session
            recommendation_id: ID рекомендации
            recommendation_type: Тип рекомендации
            target_achievement_id: ID целевого достижения
            changes: Примененные изменения
            before_evaluation: Readiness до изменений
            after_evaluation: Readiness после изменений
            before_snapshot_id: ID snapshot до изменений
            after_snapshot_id: ID snapshot после изменений
            document_id: ID документа
            started_at: Время начала выполнения
            completed_at: Время завершения

        Returns:
            RecommendationImpactMeasurement с результатами

        Raises:
            ValueError: Если версии scoring/prompt/extractor/model не совпадают
        """
        # Валидация: версии должны совпадать, иначе impact polluted
        if before_evaluation.scoring_version != after_evaluation.scoring_version:
            raise ValueError(
                f"scoring_version mismatch: before={before_evaluation.scoring_version}, "
                f"after={after_evaluation.scoring_version}. Impact measurement aborted."
            )
        if before_evaluation.extractor_version != after_evaluation.extractor_version:
            raise ValueError(
                f"extractor_version mismatch: before={before_evaluation.extractor_version}, "
                f"after={after_evaluation.extractor_version}. Impact measurement aborted."
            )
        if before_evaluation.prompt_version != after_evaluation.prompt_version:
            raise ValueError(
                f"prompt_version mismatch: before={before_evaluation.prompt_version}, "
                f"after={after_evaluation.prompt_version}. Impact measurement aborted."
            )
        if before_evaluation.model_name != after_evaluation.model_name:
            raise ValueError(
                f"model_name mismatch: before={before_evaluation.model_name}, "
                f"after={after_evaluation.model_name}. Impact measurement aborted."
            )

        # Вычисляем delta
        delta = self._compute_evaluation_delta(before_evaluation, after_evaluation)

        # Вычисляем время выполнения
        time_to_complete = (completed_at - started_at).total_seconds()

        # Сохраняем в БД
        recommendation_type_enum = self._normalize_recommendation_type(recommendation_type)
        await self._repository.create(
            session=session,
            recommendation_id=recommendation_id,
            recommendation_type=recommendation_type_enum,
            document_id=document_id,
            before_snapshot_id=before_snapshot_id,
            after_snapshot_id=after_snapshot_id,
            delta_overall=delta.delta,
            delta_components=delta.component_deltas,
        )

        # Создаем measurement
        measurement = RecommendationImpactMeasurement(
            recommendation_id=recommendation_id,
            recommendation_type=recommendation_type,
            target_achievement_id=target_achievement_id,
            execution_status=RecommendationExecutionStatus.COMPLETED,
            readiness_delta=delta,
            started_at=started_at,
            completed_at=completed_at,
            changes_made=list(changes.keys()),
            time_to_complete_seconds=time_to_complete,
        )

        return measurement

    @staticmethod
    def _normalize_recommendation_type(value: str) -> ImpactRecommendationType:
        try:
            return ImpactRecommendationType(value)
        except ValueError:
            return ImpactRecommendationType.UNKNOWN

    def _compute_evaluation_delta(
        self,
        before: ReadinessEvaluation,
        after: ReadinessEvaluation,
    ) -> ReadinessDelta:
        """Вычисляет delta между двумя readiness evaluations."""
        return ReadinessDelta(
            before_overall=before.overall_score,
            after_overall=after.overall_score,
            delta=after.overall_score - before.overall_score,
            before_components={
                "ats": before.ats_score,
                "evidence": before.evidence_score,
                "coverage": before.coverage_score,
                "quality": before.quality_score,
            },
            after_components={
                "ats": after.ats_score,
                "evidence": after.evidence_score,
                "coverage": after.coverage_score,
                "quality": after.quality_score,
            },
            component_deltas={
                "ats": after.ats_score - before.ats_score,
                "evidence": after.evidence_score - before.evidence_score,
                "coverage": after.coverage_score - before.coverage_score,
                "quality": after.quality_score - before.quality_score,
            },
        )