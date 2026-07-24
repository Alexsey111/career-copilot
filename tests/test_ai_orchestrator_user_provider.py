"""Тесты ``AIOrchestrator._resolve_client`` (#37 DeepSeek).

Per-user override резолвится лениво из ``Subscription.ai_provider``.
Нет fallback между user-провайдерами (per skill: детерминированная логика).
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.clients.base import BaseLLMClient
from app.ai.clients.deepseek import DeepSeekLLMClient
from app.ai.clients.openai import OpenAILLMClient
from app.ai.orchestrator import AIOrchestrator
from app.core.config import get_settings


class _StubClient(BaseLLMClient):
    """Заглушка для проверки резолва — provider_name фиксирован."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.aclose_calls = 0

    @property
    def provider_name(self) -> str:
        return self._name

    async def aclose(self) -> None:
        self.aclose_calls += 1

    async def generate(self, *args, **kwargs):  # pragma: no cover - stub
        raise NotImplementedError

    async def generate_structured(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


def _build_orchestrator(default_provider: str) -> AIOrchestrator:
    """Создаёт оркестратор с подменой primary client (без httpx-инициализации)."""
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.client = _StubClient(default_provider)
    orchestrator.fallback_client = None
    orchestrator.config = SimpleNamespace()
    orchestrator.ai_run_repo = None
    orchestrator._user_provider_clients = {}
    return orchestrator


class _FakeSubscriptionRepo:
    def __init__(self, ai_provider: str | None) -> None:
        self._value = ai_provider

    async def get_or_none(self, session, *, user_id):
        if self._value is None:
            return None
        return SimpleNamespace(ai_provider=self._value)


@pytest.mark.asyncio
async def test_resolve_client_returns_default_when_no_subscription(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gigachat")
    get_settings.cache_clear()
    try:
        orch = _build_orchestrator(default_provider="gigachat")
        # Подменяем repo: нет подписки
        from app.ai import orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "SubscriptionRepository", lambda: _FakeSubscriptionRepo(None))
        client, active = await orch._resolve_client(
            session=None,  # type: ignore[arg-type]
            user_id=uuid4(),
        )
    finally:
        get_settings.cache_clear()

    assert client.provider_name == "gigachat"
    assert active is False


@pytest.mark.asyncio
async def test_resolve_client_returns_default_when_ai_provider_is_none(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gigachat")
    get_settings.cache_clear()
    try:
        orch = _build_orchestrator(default_provider="gigachat")
        from app.ai import orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "SubscriptionRepository", lambda: _FakeSubscriptionRepo(None))
        client, active = await orch._resolve_client(
            session=None,  # type: ignore[arg-type]
            user_id=uuid4(),
        )
    finally:
        get_settings.cache_clear()

    assert client.provider_name == "gigachat"
    assert active is False


@pytest.mark.asyncio
async def test_resolve_client_uses_user_provider(monkeypatch):
    """user ai_provider="deepseek", settings ai_provider="gigachat" → deepseek."""
    monkeypatch.setenv("AI_PROVIDER", "gigachat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        orch = _build_orchestrator(default_provider="gigachat")
        from app.ai import orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "SubscriptionRepository", lambda: _FakeSubscriptionRepo("deepseek"))
        client, active = await orch._resolve_client(
            session=None,  # type: ignore[arg-type]
            user_id=uuid4(),
        )
    finally:
        get_settings.cache_clear()

    assert active is True
    assert client.provider_name == "deepseek"
    assert isinstance(client, DeepSeekLLMClient)
    # Cleanup — клиент попал в кэш. ``aclose`` закроет httpx-клиент внутри
    # DeepSeekLLMClient (без отдельного счётчика aclose_calls, как у stub).
    # Проверяем, что orch._user_provider_clients очищен после aclose()
    # и клиент реально закрыт (aclose отработал без ошибки).
    assert "deepseek" in orch._user_provider_clients
    await orch.aclose()
    assert orch._user_provider_clients == {}


@pytest.mark.asyncio
async def test_resolve_client_caches_user_provider(monkeypatch):
    """Повторный вызов с тем же user-провайдером → тот же инстанс из кэша."""
    monkeypatch.setenv("AI_PROVIDER", "gigachat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        orch = _build_orchestrator(default_provider="gigachat")
        from app.ai import orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "SubscriptionRepository", lambda: _FakeSubscriptionRepo("deepseek"))
        user_id = uuid4()
        c1, _ = await orch._resolve_client(session=None, user_id=user_id)  # type: ignore[arg-type]
        c2, _ = await orch._resolve_client(session=None, user_id=user_id)  # type: ignore[arg-type]
    finally:
        get_settings.cache_clear()

    assert c1 is c2
    await orch.aclose()


@pytest.mark.asyncio
async def test_resolve_client_falls_back_when_user_provider_init_fails(monkeypatch):
    """Если user-провайдер не сконфигурирован (нет ключа) → дефолт, без 5xx.

    Подвох: ``Settings`` грузит ``.env`` файл, ``monkeypatch.delenv`` не
    стирает значение с диска. Используем ``unittest.mock.patch`` для
    полного контроля над ``get_settings`` в ``app.ai.factory`` И в
    ``app.ai.clients.deepseek`` (отдельные импорты в каждом модуле).
    """
    import unittest.mock as mock
    from app.core import config as cfg

    monkeypatch.setenv("AI_PROVIDER", "gigachat")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    fake_settings = cfg.Settings.model_construct(
        _env_file=None,
        AI_PROVIDER="gigachat",
        DATABASE_URL="postgresql+asyncpg://x/x",
        SYNC_DATABASE_URL="postgresql://x/x",
        JWT_SECRET_KEY="x",
        DEEPSEEK_API_KEY=None,
    )

    with mock.patch("app.ai.factory.get_settings", return_value=fake_settings), \
         mock.patch("app.ai.clients.deepseek.get_settings", return_value=fake_settings):
        try:
            orch = _build_orchestrator(default_provider="gigachat")
            from app.ai import orchestrator as orch_mod
            monkeypatch.setattr(
                orch_mod,
                "SubscriptionRepository",
                lambda: _FakeSubscriptionRepo("deepseek"),
            )
            client, active = await orch._resolve_client(
                session=None,  # type: ignore[arg-type]
                user_id=uuid4(),
            )
        finally:
            get_settings.cache_clear()

    # Откат к дефолту, override не применён (active=False).
    assert client.provider_name == "gigachat"
    assert active is False
    assert "deepseek" not in orch._user_provider_clients


@pytest.mark.asyncio
async def test_resolve_client_active_true_when_user_explicitly_chooses_default(monkeypatch):
    """user выбрал ``"gigachat"`` (== settings.ai_provider) → active=True
    (override активен, но физически клиент = self.client)."""
    monkeypatch.setenv("AI_PROVIDER", "gigachat")
    get_settings.cache_clear()
    try:
        orch = _build_orchestrator(default_provider="gigachat")
        from app.ai import orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "SubscriptionRepository", lambda: _FakeSubscriptionRepo("gigachat"))
        client, active = await orch._resolve_client(
            session=None,  # type: ignore[arg-type]
            user_id=uuid4(),
        )
    finally:
        get_settings.cache_clear()

    assert client is orch.client
    assert active is True
