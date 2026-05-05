# app/ai/orchestrator.py
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import AIOrchestratorConfig


class AIOrchestrator:
    """Заглушка для постепенного внедрения AI-оркестрации"""

    def __init__(self, config: AIOrchestratorConfig | None = None):
        self.config = config or AIOrchestratorConfig.from_settings()

    async def execute(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        prompt_template: Any,
        prompt_vars: dict[str, Any],
        workflow_name: str,
        target_type: str,
        target_id: str | None = None,
    ) -> dict[str, Any]:
        """Временная реализация: возвращает пустой результат.

        Позже здесь будет реальная логика с LLM-клиентом, ретраями и фолбэком.
        """
        return {
            "result": "",
            "usage": {},
            "cost": 0.0,
            "model": self.config.default_model,
        }
