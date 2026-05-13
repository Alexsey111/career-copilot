# app/services/retry_policy.py

"""
Retry & Recovery for pipeline execution.

Позволяет:
- Настроить политику повторных попыток для шагов pipeline
- Возобновить выполнение с последнего успешного шага после сбоя
- Использовать разные стратегии backoff
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from uuid import UUID


class BackoffStrategy(Enum):
    """Стратегии экспоненциальной задержки между повторами."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass(slots=True)
class RetryPolicy:
    """
    Политика повторных попыток для pipeline шагов.

    Пример:
        policy = RetryPolicy(
            max_retries=3,
            retryable_steps=["document_evaluation", "readiness_scoring"],
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay_sec=1.0,
            max_delay_sec=60.0,
        )
    """
    max_retries: int = 3
    retryable_steps: list[str] = field(default_factory=list)
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay_sec: float = 1.0
    max_delay_sec: float = 60.0
    retryable_exceptions: list[type[Exception]] = field(default_factory=list)

    def is_retryable(self, step_name: str, exception: Exception | None = None) -> bool:
        """
        Проверяет, можно ли повторить шаг.

        Args:
            step_name: Имя шага
            exception: Исключение, если есть

        Returns:
            True если шаг можно повторить
        """
        # Если список retryable_steps пустой, все шаги можно повторять
        if not self.retryable_steps:
            return True

        # Проверяем, входит ли шаг в список retryable
        if step_name not in self.retryable_steps:
            return False

        # Если есть исключения для проверки
        if exception and self.retryable_exceptions:
            return any(isinstance(exception, exc) for exc in self.retryable_exceptions)

        return True

    def calculate_delay(self, attempt: int) -> float:
        """
        Вычисляет задержку перед повторной попыткой.

        Args:
            attempt: Текущий номер попытки (0-indexed)

        Returns:
            Задержка в секундах
        """
        if attempt <= 0:
            return 0.0

        match self.backoff_strategy:
            case BackoffStrategy.FIXED:
                delay = self.base_delay_sec

            case BackoffStrategy.LINEAR:
                delay = self.base_delay_sec * attempt

            case BackoffStrategy.EXPONENTIAL:
                delay = self.base_delay_sec * (2 ** (attempt - 1))

            case BackoffStrategy.EXPONENTIAL_JITTER:
                base_delay = self.base_delay_sec * (2 ** (attempt - 1))
                # Добавляем jitter ±25%
                jitter = base_delay * 0.25 * (2 * random.random() - 1)
                delay = base_delay + jitter

            case _:
                delay = self.base_delay_sec

        return min(delay, self.max_delay_sec)

    def should_retry(self, step_name: str, attempt: int, exception: Exception | None = None) -> bool:
        """
        Проверяет, нужно ли делать повторную попытку.

        Args:
            step_name: Имя шага
            attempt: Текущий номер попытки
            exception: Исключение, если есть

        Returns:
            True если нужно повторить
        """
        if attempt >= self.max_retries:
            return False

        return self.is_retryable(step_name, exception)


@dataclass(slots=True)
class RecoveryPoint:
    """Точка восстановления для pipeline."""
    step_name: str
    step_id: str
    completed_at: datetime
    output_artifact_ids: list[str]
    metadata: dict[str, Any]


@dataclass(slots=True)
class ExecutionRecoveryState:
    """Состояние восстановления выполнения."""
    execution_id: str
    last_successful_step: RecoveryPoint | None = None
    failed_step: str | None = None
    failed_at: datetime | None = None
    error_message: str | None = None
    recovered: bool = False
    recovered_at: datetime | None = None


class PipelineRecoveryManager:
    """
    Менеджер восстановления pipeline execution.

    Позволяет возобновить выполнение с последнего успешного шага.
    """

    def __init__(self) -> None:
        self._recovery_states: dict[str, ExecutionRecoveryState] = {}

    def record_step_success(
        self,
        execution_id: str,
        step_id: str,
        step_name: str,
        output_artifact_ids: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Записывает успешное завершение шага.

        Args:
            execution_id: ID выполнения pipeline
            step_id: ID шага
            step_name: Имя шага
            output_artifact_ids: IDs созданных артефактов
            metadata: Дополнительные метаданные
        """
        if execution_id not in self._recovery_states:
            self._recovery_states[execution_id] = ExecutionRecoveryState(
                execution_id=execution_id,
            )

        state = self._recovery_states[execution_id]
        state.last_successful_step = RecoveryPoint(
            step_name=step_name,
            step_id=step_id,
            completed_at=datetime.now(),
            output_artifact_ids=output_artifact_ids,
            metadata=metadata or {},
        )

    def record_step_failure(
        self,
        execution_id: str,
        step_name: str,
        error_message: str,
    ) -> None:
        """
        Записывает сбой шага.

        Args:
            execution_id: ID выполнения pipeline
            step_name: Имя шага
            error_message: Сообщение об ошибке
        """
        if execution_id not in self._recovery_states:
            self._recovery_states[execution_id] = ExecutionRecoveryState(
                execution_id=execution_id,
            )

        state = self._recovery_states[execution_id]
        state.failed_step = step_name
        state.failed_at = datetime.now()
        state.error_message = error_message

    def get_recovery_state(self, execution_id: str) -> ExecutionRecoveryState | None:
        """Получает состояние восстановления для выполнения."""
        return self._recovery_states.get(execution_id)

    def mark_recovered(self, execution_id: str) -> None:
        """Отмечает выполнение как восстановленное."""
        state = self._recovery_states.get(execution_id)
        if state:
            state.recovered = True
            state.recovered_at = datetime.now()

    def get_resumable_step(self, execution_id: str) -> str | None:
        """
        Определяет следующий шаг для возобновления.

        Args:
            execution_id: ID выполнения

        Returns:
            Имя следующего шага или None
        """
        state = self._recovery_states.get(execution_id)
        if not state:
            return None

        # Если есть последний успешный шаг, возвращаем следующий
        if state.last_successful_step:
            # Логика определения следующего шага зависит от pipeline
            # Возвращаем шаг после последнего успешного
            return self._get_next_step_after(state.last_successful_step.step_name)

        return None

    def _get_next_step_after(self, step_name: str) -> str | None:
        """
        Определяет следующий шаг после указанного.

        Это упрощенная логика - в реальной системе
        нужно использовать PipelineDefinition.
        """
        # Стандартный порядок шагов
        step_sequence = [
            "profile_loading",
            "vacancy_analysis",
            "achievement_retrieval",
            "coverage_mapping",
            "document_generation",
            "document_evaluation",
            "readiness_scoring",
            "review_gate",
        ]

        try:
            current_index = step_sequence.index(step_name)
            if current_index + 1 < len(step_sequence):
                return step_sequence[current_index + 1]
        except ValueError:
            pass

        return None


def resume_execution_from_step(
    execution_id: UUID,
    target_step: str,
    input_artifacts: dict[str, Any] | None = None,
    override_parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Возобновляет выполнение pipeline с указанного шага.

    Args:
        execution_id: ID pipeline execution для возобновления
        target_step: Имя шага, с которого начать
        input_artifacts: Артефакты для передачи шагу
        override_parameters: Переопределения параметров

    Returns:
        Словарь с информацией о возобновлении:
        {
            "success": bool,
            "execution_id": str,
            "resumed_step": str,
            "skipped_steps": list[str],
            "input_artifacts": dict,
        }

    Пример использования:
        result = resume_execution_from_step(
            execution_id=UUID("..."),
            target_step="readiness_scoring",
            input_artifacts={"resume_document": {...}},
        )

        if result["success"]:
            print(f"Возобновлено с шага: {result['resumed_step']}")
    """
    # Это placeholder-функция
    # В реальной реализации нужно:
    # 1. Загрузить состояние выполнения из репозитория
    # 2. Восстановить артефакты из last_successful_step
    # 3. Пересоздать шаги от target_step
    # 4. Запустить выполнение

    return {
        "success": True,
        "execution_id": str(execution_id),
        "resumed_step": target_step,
        "skipped_steps": [],
        "input_artifacts": input_artifacts or {},
        "override_parameters": override_parameters or {},
        "resumed_at": datetime.now().isoformat(),
    }


class StepExecutorWithRetry:
    """
    Обертка для выполнения шагов с retry policy.

    Пример использования:
        executor = StepExecutorWithRetry(retry_policy)

        result = await executor.execute_with_retry(
            step_name="document_evaluation",
            execute_func=evaluate_document,
            args=(document,),
        )
    """

    def __init__(self, retry_policy: RetryPolicy) -> None:
        self._retry_policy = retry_policy

    async def execute_with_retry(
        self,
        step_name: str,
        execute_func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any | None, int, Exception | None]:
        """
        Выполняет шаг с повторными попытками.

        Args:
            step_name: Имя шага
            execute_func: Функция выполнения шага
            *args: Позиционные аргументы для функции
            **kwargs: Именованные аргументы для функции

        Returns:
            (result, attempts_made, exception_if_failed)
        """
        last_exception: Exception | None = None
        attempt = 0

        while True:
            try:
                result = await execute_func(*args, **kwargs)
                return result, attempt + 1, None

            except Exception as e:
                last_exception = e
                attempt += 1

                if not self._retry_policy.should_retry(step_name, attempt, e):
                    return None, attempt, e

                # Вычисляем задержку
                delay = self._retry_policy.calculate_delay(attempt)
                await self._sleep(delay)

        # unreachable
        return None, attempt, last_exception

    @staticmethod
    async def _sleep(seconds: float) -> None:
        """Асинхронная задержка."""
        import asyncio
        await asyncio.sleep(seconds)
