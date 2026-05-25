from __future__ import annotations

import pytest

from app.ai.clients.gigachat import GigaChatClient
from app.ai.clients.mock import MockLLMClient
from app.ai.clients.openai import OpenAILLMClient
from app.ai.factory import create_llm_client
from app.core.config import get_settings


def test_create_mock_llm_client():
    client = create_llm_client("mock")

    assert isinstance(client, MockLLMClient)
    assert client.provider_name == "mock"


def test_create_openai_llm_client_uses_config(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.openai.local/v1")
    monkeypatch.setenv("OPENAI_TIMEOUT", "12.5")
    get_settings.cache_clear()

    try:
        client = create_llm_client("openai")

        assert isinstance(client, OpenAILLMClient)
        assert client.provider_name == "openai"
        assert client.base_url == "https://example.openai.local/v1"
    finally:
        get_settings.cache_clear()


def test_create_openai_llm_client_requires_config(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
            create_llm_client("openai")
    finally:
        get_settings.cache_clear()


def test_create_gigachat_llm_client_requires_config(monkeypatch):
    monkeypatch.setenv("GIGACHAT_API_KEY", "")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError):
            create_llm_client("gigachat")
    finally:
        get_settings.cache_clear()


def test_create_unknown_llm_provider_rejects():
    with pytest.raises(ValueError, match="Unsupported AI provider"):
        create_llm_client("unknown")
