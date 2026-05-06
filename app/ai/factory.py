from __future__ import annotations

from app.ai.clients.gigachat import GigaChatClient
from app.ai.orchestrator import AIOrchestrator


def create_ai_orchestrator() -> AIOrchestrator:
    """Единая точка создания AI-оркестратора.

    Используется во всех сервисах и роутах, которым нужен AI.
    Гарантирует единую конфигурацию клиента и упрощает
    добавление fallback / multi-provider в будущем.

    Returns:
        Настроенный экземпляр AIOrchestrator.
    """
    client = GigaChatClient()
    return AIOrchestrator(client=client)
