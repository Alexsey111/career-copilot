# app\api\ai\clients\base.py

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMClientError(Exception):
    """Базовое исключение для ошибок LLM-клиента"""
    
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


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