# app\api\ai\clients\base.py

from __future__ import annotations

import ssl
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import certifi


class LLMClientError(Exception):
    """Базовое исключение для ошибок LLM-клиента"""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


def resolve_llm_verify(settings: Any) -> "ssl.SSLContext | bool":
    """Значение ``verify`` для ``httpx.AsyncClient`` по настройкам SSL.

    Возвращает:
    - ``SSLContext`` если задан ``AI_SSL_CA_BUNDLE`` — системный trust
      (certifi) + доп. PEM с CA (Root CA антивируса/корпоративного прокси).
      Обычные сайты тоже работают — system trust сохранён. Безопасный способ
      для dev-сред с MITM-прокси.
    - ``settings.ai_ssl_verify`` (bool) — ``True`` (прод, system trust) или
      ``False`` (dev, проверка отключена — MITM-риск).

    Если ``AI_SSL_CA_BUNDLE`` указан, но файл не найден — поднимаем
    ``LLMClientError`` (retryable=False): тихо игнорировать нельзя, иначе
    LLM-клиент молча падает на SSL и улучшения degraded без понятной причины.
    """
    ca_bundle = settings.ai_ssl_ca_bundle
    if not isinstance(ca_bundle, str) or not ca_bundle.strip():
        return settings.ai_ssl_verify
    ca_bundle = ca_bundle.strip()
    if not Path(ca_bundle).is_file():
        raise LLMClientError(
            f"AI_SSL_CA_BUNDLE file not found: {ca_bundle}", retryable=False
        )
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cafile=ca_bundle)
    return context


class BaseLLMClient(ABC):
    """Абстрактный интерфейс LLM-клиента"""
    
    @abstractmethod
    async def aclose(self) -> None:
        """Закрывает HTTP-клиент и освобождает соединения."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        Генерация ответа от LLM.
        
        Returns:
            dict с ключами:
            - content: str (текст ответа)
            - usage: dict(prompt_tokens, completion_tokens, total_tokens)
            - model: str (использованная модель)
            - finish_reason: str
        """
        pass
    
    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any],
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """
        Генерация с валидацией по JSON-схеме.
        Должен возвращать только валидный JSON или бросать ошибку.
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Название провайдера (gigachat, yandex, openai...)"""
        pass