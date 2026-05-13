# app/services/review_action_loop.py

"""
Review Action Loop — recommendation execution feedback loop.

Killer feature:
- task completed → rerun evaluation → compute delta → compare readiness → measure impact

Пользователь видит:
"Добавление метрики повысило readiness с 0.62 до 0.74"

Это real copilot UX — видно прямое влияние действий.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.impact_measurement_repository import ImpactMeasurementRepository


class RecommendationExecutionStatus(Enum):
    """Статус выполнения рекомендации."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(slots=True)
class ReadinessDelta:
    """Изменение readiness score после выполнения рекомендации."""
    before_overall: float
    after_overall: float
    delta: float

    # Компонентные изменения
    before_components: dict[str, float] = field(default_factory=dict)
    after_components: dict[str, float] = field(default_factory=dict)
    component_deltas: dict[str, float] = field(default_factory=dict)

    @property
    def improvement(self) -> bool:
        """Проверяет, улучшился ли score."""
        return self.delta > 0

    @property
    def improvement_percentage(self) -> float:
        """Процент улучшения."""
        if self.before_overall == 0:
            return 0.0
        return (self.delta / self.before_overall) * 100


@dataclass(slots=True)
class RecommendationImpactMeasurement:
    """Измеренное влияние выполненной рекомендации."""
    recommendation_id: str
    recommendation_type: str
    target_achievement_id: str | None
    execution_status: RecommendationExecutionStatus
    started_at: datetime
    completed_at: datetime | None = None
    readiness_delta: ReadinessDelta | None = None
    changes_made: list[str] = field(default_factory=list)
    notes: str = ""
    time_to_complete_seconds: float | None = None
    user_confirmed_impact: bool = False


@dataclass(slots=True)
class ImpactReport:
    """Отчет о влиянии рекомендаций."""
    recommendation_id: str
    description: str
    readiness_before: float
    readiness_after: float
    readiness_delta: float
    completed_at: datetime

    # Component breakdown
    ats_delta: float = 0.0
    evidence_delta: float = 0.0
    coverage_delta: float = 0.0
    quality_delta: float = 0.0
    time_to_complete_seconds: float | None = None

    @property
    def impact_summary(self) -> str:
        """Краткое описание влияния."""
        if self.readiness_delta > 0:
            return f"Readiness повысился с {self.readiness_before:.2f} до {self.readiness_after:.2f} (+{self.readiness_delta:.2f})"
        elif self.readiness_delta < 0:
            return f"Readiness изменился с {self.readiness_before:.2f} до {self.readiness_after:.2f} ({self.readiness_delta:.2f})"
        return f"Readiness остался на уровне {self.readiness_before:.2f}"


class RecommendationExecutor:
    """
    Исполнитель рекомендаций с измерением impact.

    Основной цикл:
    1. Получить recommendation_task
    2. Выполнить изменение в документе (через DocumentMutationService)
    3. Пересчитать readiness score
    4. Вычислить delta
    5. Записать impact measurement
    """

    def __init__(
        self,
        readiness_evaluation_service: Any,  # ReadinessEvaluationService
        document_mutation_service: Any,  # DocumentMutationService
        impact_measurement_service: Any,  # ImpactMeasurementService
        artifact_registry: Any,  # ArtifactRegistry
        impact_measurement_repository: ImpactMeasurementRepository,
    ) -> None:
        self._evaluation_service = readiness_evaluation_service
        self._mutation_service = document_mutation_service
        self._impact_service = impact_measurement_service
        self._artifact_registry = artifact_registry
        self._impact_repository = impact_measurement_repository
        self._impact_measurements: dict[str, RecommendationImpactMeasurement] = {}

    async def execute_recommendation(
        self,
        session: AsyncSession,
        recommendation_task_id: str,
        document_id: UUID,
        changes: dict[str, Any],
        user_id: UUID,
    ) -> RecommendationImpactMeasurement:
        """
        Выполняет рекомендацию и измеряет impact.

        Application-level transaction orchestration:
        - snapshots
        - lineage
        - impact measurements

        Args:
            session: Database session
            recommendation_task_id: ID задачи рекомендации
            document_id: ID документа для изменения
            changes: Изменения для применения
            user_id: ID пользователя

        Returns:
            RecommendationImpactMeasurement с результатами
        """
        async with session.begin():
            started_at = datetime.now(timezone.utc)

            # 1. Получаем текущий readiness evaluation через ReadinessEvaluationService
            before_evaluation, before_snapshot_id = await self._evaluation_service.evaluate_document(
                session=session,
                document_id=document_id,
                user_id=user_id,
            )

            # 2. Применяем изменения через DocumentMutationService (создаёт новую версию)
            new_document = await self._mutation_service.apply_changes(
                session=session,
                document_id=document_id,
                changes=changes,
                user_id=user_id,
                change_reason=f"Recommendation: {recommendation_task_id}",
            )

            # 3. Пересчитываем readiness через ReadinessEvaluationService для новой версии
            after_evaluation, after_snapshot_id = await self._evaluation_service.evaluate_document(
                session=session,
                document_id=new_document.id,
                user_id=user_id,
            )

            # 4. Измеряем impact через ImpactMeasurementService
            completed_at = datetime.now(timezone.utc)
            measurement = await self._impact_service.measure_impact(
                session=session,
                recommendation_id=recommendation_task_id,
                recommendation_type=changes.get("type", "unknown"),
                target_achievement_id=changes.get("target_achievement_id"),
                changes=changes,
                before_evaluation=before_evaluation,
                after_evaluation=after_evaluation,
                before_snapshot_id=before_snapshot_id,
                after_snapshot_id=after_snapshot_id,
                document_id=new_document.id,
                started_at=started_at,
                completed_at=completed_at,
            )

            self._impact_measurements[recommendation_task_id] = measurement

            return measurement

    def get_impact_measurement(self, recommendation_id: str) -> RecommendationImpactMeasurement | None:
        """Получает измерение impact для рекомендации."""
        return self._impact_measurements.get(recommendation_id)

    def get_all_impact_measurements(self) -> list[RecommendationImpactMeasurement]:
        """Получает все измерения impact."""
        return list(self._impact_measurements.values())


class ReviewActionLoop:
    """
    Основной цикл Review Action Loop.

    Управление полным процессом:
    1. Пользователь получает recommendations
    2. Пользователь выполняет рекомендации
    3. Система автоматически пересчитывает readiness
    4. Показывает impact каждого действия

    Пример использования:
        loop = ReviewActionLoop(executor, artifact_registry)

        # Пользователь завершил рекомендацию
        impact = await loop.on_recommendation_completed(
            recommendation_id="rec-123",
            document_id=document_uuid,
            changes={"add_metric": {"value": "increased revenue by 30%"}},
        )

        print(f"Readiness improved by {impact.readiness_delta.delta:.2f}")
    """

    def __init__(
        self,
        executor: RecommendationExecutor,
        artifact_registry: Any,  # ArtifactRegistry
    ) -> None:
        self._executor = executor
        self._artifact_registry = artifact_registry

    async def on_recommendation_completed(
        self,
        session: AsyncSession,
        recommendation_id: str,
        document_id: UUID,
        changes: dict[str, Any],
        user_id: UUID,
    ) -> RecommendationImpactMeasurement:
        """
        Обработчик завершения рекомендации.

        Args:
            session: Database session
            recommendation_id: ID рекомендации
            document_id: ID измененного документа
            changes: Примененные изменения
            user_id: ID пользователя

        Returns:
            Измеренный impact
        """
        # Выполняем рекомендацию и измеряем impact
        measurement = await self._executor.execute_recommendation(
            session=session,
            recommendation_id=recommendation_id,
            document_id=document_id,
            changes=changes,
            user_id=user_id,
        )

        # Регистрируем новый artifact (обновленный документ)
        if self._artifact_registry:
            self._artifact_registry.register(
                artifact_id=f"doc-{document_id}-v{measurement.completed_at.timestamp()}",
                artifact_type="resume",
                source_execution_id="manual-update",
                version="v2.0",
                payload={"document_id": str(document_id), "changes": changes},
                parent_artifact_ids=[f"doc-{document_id}-v1"],
            )

        return measurement

    async def get_impact_report(
        self,
        recommendation_id: str,
    ) -> ImpactReport | None:
        """
        Генерирует отчет о влиянии рекомендации.

        Args:
            recommendation_id: ID рекомендации

        Returns:
            ImpactReport с детализацией
        """
        measurement = self._executor.get_impact_measurement(recommendation_id)
        if not measurement or not measurement.readiness_delta:
            return None

        delta = measurement.readiness_delta

        return ImpactReport(
            recommendation_id=recommendation_id,
            description=f"Реализация рекомендации {recommendation_id}",
            readiness_before=delta.before_overall,
            readiness_after=delta.after_overall,
            readiness_delta=delta.delta,
            ats_delta=delta.component_deltas.get("ats", 0.0),
            evidence_delta=delta.component_deltas.get("evidence", 0.0),
            coverage_delta=delta.component_deltas.get("coverage", 0.0),
            quality_delta=delta.component_deltas.get("quality", 0.0),
            completed_at=measurement.completed_at or datetime.now(timezone.utc),
            time_to_complete_seconds=measurement.time_to_complete_seconds,
        )

    async def get_user_impact_summary(self, user_id: UUID) -> dict[str, Any]:
        """
        Генерирует сводку влияния для пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Сводная статистика impact
        """
        measurements = self._executor.get_all_impact_measurements()

        if not measurements:
            return {
                "total_recommendations_completed": 0,
                "total_readiness_improvement": 0.0,
                "average_improvement_per_recommendation": 0.0,
                "recommendations_by_type": {},
            }

        total_improvement = sum(
            m.readiness_delta.delta if m.readiness_delta else 0.0
            for m in measurements
        )

        completed = [m for m in measurements if m.execution_status == RecommendationExecutionStatus.COMPLETED]
        avg_improvement = total_improvement / len(completed) if completed else 0.0

        # Группировка по типам
        by_type: dict[str, list[RecommendationImpactMeasurement]] = {}
        for m in measurements:
            if m.recommendation_type not in by_type:
                by_type[m.recommendation_type] = []
            by_type[m.recommendation_type].append(m)

        return {
            "total_recommendations_completed": len(completed),
            "total_readiness_improvement": total_improvement,
            "average_improvement_per_recommendation": avg_improvement,
            "recommendations_by_type": {
                t: {
                    "count": len(items),
                    "total_delta": sum(m.readiness_delta.delta if m.readiness_delta else 0.0 for m in items),
                }
                for t, items in by_type.items()
            },
        }


def format_impact_message(impact: RecommendationImpactMeasurement) -> str:
    """
    Форматирует сообщение о влиянии для пользователя.

    Пример вывода:
        "Добавление метрики повысило readiness с 0.62 до 0.74 (+0.12)"
    """
    if not impact.readiness_delta:
        return "Impact не измерен"

    delta = impact.readiness_delta

    if delta.improvement:
        return (
            f"Readiness повысился с {delta.before_overall:.2f} "
            f"до {delta.after_overall:.2f} (+{delta.delta:.2f})"
        )
    elif delta.delta < 0:
        return (
            f"Readiness изменился с {delta.before_overall:.2f} "
            f"до {delta.after_overall:.2f} ({delta.delta:.2f})"
        )
    return f"Readiness остался на уровне {delta.before_overall:.2f}"
