# app\api\ai\config.py

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.core.config import get_settings


class AIModel(str, Enum):
    """Поддерживаемые модели"""

    GIGACHAT_PRO = "gigachat-pro"
    GIGACHAT_LITE = "gigachat-lite"


class AIOrchestratorConfig(BaseModel):
    # Модель по умолчанию
    default_model: str = Field(default="gigachat-pro", description="Default LLM model")
    
    # Таймауты и ретраи
    request_timeout_sec: float = Field(default=30.0)
    max_retries: int = Field(default=3)
    retry_backoff_sec: float = Field(default=2.0)
    
    # Лимиты
    max_tokens: int = Field(default=2048)
    temperature: float = Field(default=0.1)  # низкая для детерминизма
    
    # Трассировка
    enable_tracing: bool = Field(default=True)
    
    # Cost tracking (опционально)
    cost_per_1k_tokens_input: float = Field(default=0.0)
    cost_per_1k_tokens_output: float = Field(default=0.0)
    
    @classmethod
    def from_settings(cls) -> "AIOrchestratorConfig":
        settings = get_settings()
        return cls(
            default_model=settings.ai_default_model,
            request_timeout_sec=settings.ai_request_timeout,
            max_retries=settings.ai_max_retries,
            temperature=settings.ai_temperature,
        )