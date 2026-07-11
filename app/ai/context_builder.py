# app\ai\context_builder.py

"""Слой сборки контекста промпта (ТЗ §3.4, pipeline-слой «ContextBuilder»).

Нормализует переменные промпта перед рендерингом:
- ограничивает длину строковых значений (бюджет контекста, защита от
  раздувания prompt и утечки через snapshot);
- присоединяет ``language``, если спецификация промпта его ожидает.

Это выделение слоя сборки контекста из orchestrator: use_cases формируют
сырые доменные данные, ContextBuilder приводим их к безопасному виду,
оркестратор рендерит шаблон.
"""

from __future__ import annotations

from typing import Any

DEFAULT_MAX_FIELD_LENGTH = 8000

# Дефолты локализации промпта RESUME_TAILOR_V1 (Этап 7). Подставляются, когда
# вызывающий код (например, инфраструктурные тесты orchestrator) не передаёт
# market явно — аналогично тому, как подставляется language. Реальный use case
# (tailor_resume) передаёт явные значения, перекрывая дефолт.
_DEFAULT_MARKET_LABEL = "российского рынка труда"
_DEFAULT_SECTION_LANGUAGE = "русском"


class ContextBuilder:
    def __init__(self, max_field_length: int = DEFAULT_MAX_FIELD_LENGTH) -> None:
        self._max_field_length = max_field_length

    def normalize(
        self,
        prompt_vars: dict[str, Any],
        *,
        spec_input_keys: list[str] | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in prompt_vars.items():
            result[key] = self._truncate(value)

        if language is not None and spec_input_keys and "language" in spec_input_keys:
            result.setdefault("language", language)

        if spec_input_keys:
            if "market_label" in spec_input_keys:
                result.setdefault("market_label", _DEFAULT_MARKET_LABEL)
            if "section_language" in spec_input_keys:
                result.setdefault("section_language", _DEFAULT_SECTION_LANGUAGE)

        return result

    def _truncate(self, value: Any) -> Any:
        if isinstance(value, str) and len(value) > self._max_field_length:
            return value[: self._max_field_length]
        return value