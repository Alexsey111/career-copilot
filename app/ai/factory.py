from __future__ import annotations

from app.ai.clients.base import BaseLLMClient
from app.ai.clients.gigachat import GigaChatClient
from app.ai.clients.mock import MockLLMClient
from app.ai.clients.openai import OpenAILLMClient
from app.ai.config import AIOrchestratorConfig
from app.ai.orchestrator import AIOrchestrator
from app.core.config import get_settings
from app.repositories.ai_run_repository import AIRunRepository


def create_llm_client(provider: str) -> BaseLLMClient:
    normalized = provider.strip().lower()

    if normalized == "gigachat":
        return GigaChatClient()

    if normalized == "openai":
        return OpenAILLMClient()

    if normalized == "mock":
        return MockLLMClient()

    raise ValueError(f"Unsupported AI provider: {provider}")


def create_ai_orchestrator() -> AIOrchestrator:
    settings = get_settings()
    config = AIOrchestratorConfig.from_settings()

    client = create_llm_client(settings.ai_provider)

    fallback_client = None
    if settings.ai_fallback_provider:
        fallback_client = create_llm_client(settings.ai_fallback_provider)

    # Конструируем через __new__, минуя __init__: __init__ при отсутствии
    # client/fallback_client сам вызвал бы фабрику (лишние создания клиентов).
    # Тесты также патчат __init__ — этот путь остаётся стабильным.
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.client = client
    orchestrator.config = config
    orchestrator.fallback_client = fallback_client
    orchestrator.ai_run_repo = AIRunRepository()
    return orchestrator