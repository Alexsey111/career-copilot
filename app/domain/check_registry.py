from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TypeVar

from app.domain.coverage_eval_models import CoverageCheckResult
from app.domain.coverage_models import RequirementCoverage

T = TypeVar("T")


class BaseDeterministicCheck(ABC):
    """Базовый класс для детерминированных проверок."""

    name: str
    severity: str = "warning"

    @abstractmethod
    def run(self, coverage: list[RequirementCoverage]) -> CoverageCheckResult:
        """Выполняет проверку."""
        ...

    @property
    def is_critical(self) -> bool:
        return self.severity == "critical"


class CoverageCheckRegistry:
    """Регистр проверок покрытия."""

    def __init__(self) -> None:
        self._checks: dict[str, BaseDeterministicCheck] = {}

    def register(self, check: BaseDeterministicCheck) -> None:
        """Регистрирует проверку."""
        self._checks[check.name] = check

    def unregister(self, name: str) -> None:
        """Удаляет проверку из регистра."""
        self._checks.pop(name, None)

    def get(self, name: str) -> BaseDeterministicCheck | None:
        """Получает проверку по имени."""
        return self._checks.get(name)

    def run_all(self, coverage: list[RequirementCoverage]) -> list[CoverageCheckResult]:
        """Выполняет все зарегистрированные проверки."""
        results: list[CoverageCheckResult] = []
        for check in self._checks.values():
            results.append(check.run(coverage))
        return results

    @property
    def check_names(self) -> Sequence[str]:
        """Список имён зарегистрированных проверок."""
        return tuple(self._checks.keys())
