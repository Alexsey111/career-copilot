"""Тесты factory-dispatch для DeepSeek (#37 DeepSeek)."""

from __future__ import annotations

import pytest

from app.ai.clients.deepseek import DeepSeekLLMClient
from app.ai.factory import create_llm_client
from app.core.config import get_settings


def test_create_deepseek_llm_client_uses_config(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.deepseek.local/v1")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT", "15.0")
    get_settings.cache_clear()

    try:
        client = create_llm_client("deepseek")
    finally:
        get_settings.cache_clear()

    assert isinstance(client, DeepSeekLLMClient)
    assert client.provider_name == "deepseek"
    assert client.base_url == "https://example.deepseek.local/v1"


def test_create_deepseek_llm_client_requires_config(monkeypatch):
    """Без DEEPSEEK_API_KEY конструктор DeepSeekLLMClient должен упасть.

    Подвох: ``Settings`` (pydantic-settings) грузит ``.env`` файл, и
    ``monkeypatch.delenv`` не убирает значение, прочитанное с диска. Решение:
    подменяем ``create_llm_client`` напрямую: вызываем ``DeepSeekLLMClient()``
    в среде, где ``get_settings`` отдаёт ``Settings`` с ``deepseek_api_key=None``.
    Используем ``unittest.mock.patch`` (надёжнее ``monkeypatch.setattr`` для
    multi-module patch).
    """
    import unittest.mock as mock
    from app.core import config as cfg

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    # Полный сброс: создаём Settings, который не читает ни .env, ни os.environ.
    fake_settings = cfg.Settings.model_construct(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://x/x",
        SYNC_DATABASE_URL="postgresql://x/x",
        JWT_SECRET_KEY="x",
        DEEPSEEK_API_KEY=None,
    )

    with mock.patch("app.ai.factory.get_settings", return_value=fake_settings), \
         mock.patch("app.ai.clients.deepseek.get_settings", return_value=fake_settings):
        try:
            with pytest.raises(ValueError, match="DEEPSEEK_API_KEY is not set"):
                create_llm_client("deepseek")
        finally:
            get_settings.cache_clear()
