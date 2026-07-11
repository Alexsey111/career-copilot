# app\ai\model_router.py

"""Слой маршрутизации модели (ТЗ §3.4, pipeline-слой «ModelRouter»).

Централизует выбор модели для AI-запроса. Приоритет:
    1. явный model_override от вызывающего кода;
    2. per-workflow переопределение из карты маршрутизации;
    3. model_hint из спецификации промпта;
    4. default_model из конфига.

Карта ``_WORKFLOW_MODEL_OVERRIDES`` позволяет направлять отдельные workflow на
более дешёвую/мощную модель без правки use_cases. Сейчас карта пуста —
поведение обратно совместимо с прежней логикой выбора.
"""

from __future__ import annotations

from typing import Any


_WORKFLOW_MODEL_OVERRIDES: dict[str, str] = {}


class ModelRouter:
    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self._overrides = overrides if overrides is not None else _WORKFLOW_MODEL_OVERRIDES

    def select_model(
        self,
        *,
        workflow_name: str,
        model_override: Any = None,
        model_hint: str | None = None,
        default_model: str,
    ) -> str:
        if model_override:
            return str(model_override)
        workflow_override = self._overrides.get(workflow_name)
        if workflow_override:
            return workflow_override
        if model_hint:
            return model_hint
        return default_model