# app/domain/markets.py

from __future__ import annotations

from typing import Literal

# Поддерживаемые юрисдикции/рынки для переключателя локализации резюме и
# privacy-политик (Этап 7). RU — дефолт продукта; EU/US — anti-discrimination
# режимы (фото/возраст/пол не включаются в резюме).
Market = Literal["RU", "EU", "US"]

SUPPORTED_MARKETS: tuple[str, ...] = ("RU", "EU", "US")
DEFAULT_MARKET = "ru"  # lower-case ключ словарей локализации


def normalize_market(value: str | None) -> str:
    """Нормализация значения рынка к нижнему регистру ключа словарей локализации;
    None → DEFAULT_MARKET.

    Возвращает lower-case ключ ("ru"/"eu"/"us"), используемый в словарях
    локализации рендерера и промпта. Валидация значения (upper) выполняется
    Pydantic Literal в схемах; здесь — безопасный дефолт при отсутствии/некорректе.
    """
    if not value:
        return DEFAULT_MARKET
    normalized = value.strip().upper()
    if normalized not in SUPPORTED_MARKETS:
        return DEFAULT_MARKET
    return normalized.lower()