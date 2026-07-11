# app\ai\cache.py

"""In-process LRU-кэш ответов AI (ТЗ §3.4 «caching»).

Кэш — модульный singleton (разделяется между orchestrator-инстансами в рамках
процесса), чтобы один и тот же запрос не пересчитывался на каждом запросе
пользователя. Ключ — детерминированный хеш от шаблона/модели/температуры и
отрендеренного промпта. В многопроцессном деплое каждый воркер имеет свой
кэш (общий кэш на уровне БД — отдельная задача); для ТЗ этого достаточно.

По умолчанию отключён (``AI_CACHE_ENABLED=false``).
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from threading import Lock
from typing import Any


class AICache:
    def __init__(self, max_size: int = 256) -> None:
        self._max_size = max(max_size, 1)
        self._store: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._store.get(key)
            if value is not None:
                # Перемещаем в конец (наиболее свежий).
                self._store.move_to_end(key)
            return value

    def set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


_cache: AICache | None = None


def get_cache(max_size: int = 256) -> AICache:
    global _cache
    if _cache is None:
        _cache = AICache(max_size=max_size)
    return _cache


def reset_cache_for_tests() -> None:
    """Сброс singleton-а между тестами."""
    global _cache
    _cache = None


def make_cache_key(
    *,
    prompt_version: str,
    model: str,
    temperature: float,
    prompt: str,
) -> str:
    payload = f"{prompt_version}|{model}|{temperature}|{prompt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()