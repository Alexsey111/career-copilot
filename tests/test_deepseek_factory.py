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
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY is not set"):
            create_llm_client("deepseek")
    finally:
        get_settings.cache_clear()
