# app/services/trend_service.py

"""
Trend Service — вычисление трендов метрик с enforced comparable windows.

Гарантии:
- Previous period = текущий период - duration(current)
- Пример: current: 2026-05-01 → 2026-05-07, previous: 2026-04-24 → 2026-04-30
- Нельзя сравнить несопоставимые окна (7 дней vs 30 дней)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.execution_metrics import (
    ExecutionMetrics,
    MetricTimeWindow,
    TrendMetrics,
)
from app.services.metrics_aggregator import MetricsAggregator


@dataclass
class TimeWindow:
    """Временное окно с явными границами."""
    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def __post_init__(self) -> None:
        if self.start.tzinfo is None:
            self.start = self.start.replace(tzinfo=timezone.utc)
        else:
            self.start = self.start.astimezone(timezone.utc)
        if self.end.tzinfo is None:
            self.end = self.end.replace(tzinfo=timezone.utc)
        else:
            self.end = self.end.astimezone(timezone.utc)
        if self.end <= self.start:
            raise ValueError("TimeWindow end must be after start")


class TrendService:
    """
    Сервис для вычисления трендов с enforced comparable windows.

    Архитектурный поток:
    1. Вычисляется current period (например, LAST_7D)
    2. Автоматически вычисляется previous period = current.start - duration
    3. Запрашиваются метрики для обоих периодов
    4. Вычисляется тренд

    Пример использования:
        service = TrendService(aggregator)

        async with session.begin():
            # Автоматически вычислит previous period
            trend = await service.get_trend(
                session=session,
                metric_name="resume_success_rate",
                time_window=MetricTimeWindow.LAST_7D,
            )
    """

    def __init__(self, aggregator: MetricsAggregator) -> None:
        self._aggregator = aggregator

    def _calculate_time_windows(
        self,
        time_window: MetricTimeWindow,
        reference_date: Optional[datetime] = None,
    ) -> tuple[TimeWindow, TimeWindow]:
        """
        Вычисляет current и previous time windows.

        Гарантирует сопоставимые окна:
        - current: [now - duration, now]
        - previous: [now - 2*duration, now - duration]

        Raises:
            ValueError: Если попытка сравнить несопоставимые окна
        """
        now = reference_date or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        match time_window:
            case MetricTimeWindow.LAST_24H:
                duration = timedelta(hours=24)
            case MetricTimeWindow.LAST_7D:
                duration = timedelta(days=7)
            case MetricTimeWindow.LAST_30D:
                duration = timedelta(days=30)
            case MetricTimeWindow.LAST_90D:
                duration = timedelta(days=90)
            case MetricTimeWindow.ALL_TIME:
                raise ValueError("ALL_TIME trend comparison is not supported")

        # Current window
        current_start = now - duration
        current_window = TimeWindow(
            start=current_start,
            end=now,
        )

        # Previous window = current_start - duration до current_start
        previous_start = current_start - duration
        previous_window = TimeWindow(
            start=previous_start,
            end=current_start,
        )

        return current_window, previous_window

    async def get_trend(
        self,
        session: AsyncSession,
        metric_name: str,
        time_window: MetricTimeWindow,
        reference_date: Optional[datetime] = None,
    ) -> TrendMetrics:
        """
        Вычисляет тренд для метрики с автоматическим расчётом previous period.

        Args:
            session: Database session
            metric_name: Имя метрики
            time_window: Временное окно (определяет duration)
            reference_date: Опорная дата (по умолчанию now)

        Returns:
            TrendMetrics с current, previous, delta и direction

        Raises:
            ValueError: Если попытка сравнить несопоставимые периоды
        """
        # Вычисляем сопоставимые окна
        current_window, previous_window = self._calculate_time_windows(
            time_window, reference_date
        )

        # Получаем метрики для обоих периодов
        current_metrics = await self._aggregator.get_metrics_for_range(
            session=session,
            start_time=current_window.start,
            end_time=current_window.end,
        )

        previous_metrics = await self._aggregator.get_metrics_for_range(
            session=session,
            start_time=previous_window.start,
            end_time=previous_window.end,
        )

        # Вычисляем тренд
        return self._compute_trend(metric_name, current_metrics, previous_metrics)

    async def get_trend_comparison(
        self,
        session: AsyncSession,
        metric_name: str,
        current_window: TimeWindow,
        previous_window: TimeWindow,
    ) -> TrendMetrics:
        """
        Вычисляет тренд для явных временных окон.

        Проверяет, что окна сопоставимы (одинаковая длительность).

        Raises:
            ValueError: Если duration окон не совпадает
        """
        # Enforce comparable windows
        if current_window.duration != previous_window.duration:
            raise ValueError(
                f"Incomparable windows: current={current_window.duration}, "
                f"previous={previous_window.duration}. "
                f"Both windows must have the same duration."
            )
        if current_window.start != previous_window.end:
            raise ValueError(
                "Incomparable windows: previous window must end exactly where "
                "current window starts."
            )

        # Получаем метрики
        current_metrics = await self._aggregator.get_metrics_for_range(
            session=session,
            start_time=current_window.start,
            end_time=current_window.end,
        )

        previous_metrics = await self._aggregator.get_metrics_for_range(
            session=session,
            start_time=previous_window.start,
            end_time=previous_window.end,
        )

        return self._compute_trend(metric_name, current_metrics, previous_metrics)

    def _compute_trend(
        self,
        metric_name: str,
        current: ExecutionMetrics,
        previous: ExecutionMetrics,
    ) -> TrendMetrics:
        """Вычисляет тренд из двух наборов метрик."""
        value_map = {
            "completion_rate": current.success_rate.completion_rate,
            "failure_rate": current.failures.critical_failure_rate,
            "review_required_rate": current.reviews.review_required_rate,
            "recommendation_completion_rate": current.recommendations.recommendation_completion_rate,
            "resume_success_rate": current.resumes.resume_success_rate,
            "average_duration": current.durations.average_pipeline_duration_seconds,
            "success_rate": current.success_rate.success_rate,
            "ready_rate": current.resumes.ready_rate,
        }

        current_value = value_map.get(metric_name)
        if current_value is None:
            raise ValueError(f"Unknown metric: {metric_name}")

        prev_map = {
            "completion_rate": previous.success_rate.completion_rate,
            "failure_rate": previous.failures.critical_failure_rate,
            "review_required_rate": previous.reviews.review_required_rate,
            "recommendation_completion_rate": previous.recommendations.recommendation_completion_rate,
            "resume_success_rate": previous.resumes.resume_success_rate,
            "average_duration": previous.durations.average_pipeline_duration_seconds,
            "success_rate": previous.success_rate.success_rate,
            "ready_rate": previous.resumes.ready_rate,
        }

        previous_value = prev_map.get(metric_name, 0.0)

        delta = current_value - previous_value
        delta_percentage = (delta / previous_value * 100) if previous_value != 0 else 0.0

        # Determine direction
        if abs(delta) < 0.01:
            direction = "stable"
        elif metric_name in ["failure_rate", "review_required_rate"]:
            direction = "improving" if delta < 0 else "degrading"
        else:
            direction = "improving" if delta > 0 else "degrading"

        return TrendMetrics(
            metric_name=metric_name,
            current_value=current_value,
            previous_value=previous_value,
            delta=delta,
            delta_percentage=delta_percentage,
            direction=direction,
        )
