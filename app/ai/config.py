# app/ai/config.py
from __future__ import annotations

from pydantic import BaseModel, Field


class AIOrchestratorConfig(BaseModel):
    """Конфигурация AI-оркестратора"""

    default_model: str = Field(default="gigachat-pro", description="Default LLM model")
    max_retries: int = Field(default=3, ge=1)
    retry_backoff_sec: float = Field(default=1.0, ge=0)

    @classmethod
    def from_settings(cls) -> "AIOrchestratorConfig":
        return cls()
