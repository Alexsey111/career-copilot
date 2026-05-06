"""
Тесты для safe_render_prompt: безопасность подстановки в промпты
"""

from __future__ import annotations

import pytest

from app.ai.registry.prompts import safe_render_prompt, PromptRenderingError


def test_safe_render_basic():
    """Базовая подстановка переменных"""
    template = "Привет, {name}! Ты изучаешь {language}."
    result = safe_render_prompt(template, {"name": "Алекс", "language": "Python"})
    assert result == "Привет, Алекс! Ты изучаешь Python."


def test_safe_render_with_json_braces():
    """Шаблон с JSON-примерами (двойные скобки)"""
    template = """
Выведи JSON в формате:
{{
  "summary": "...",
  "skills": ["...", "..."]
}}
""".strip()
    result = safe_render_prompt(template, {})
    # Двойные скобки должны остаться одинарными
    assert '"summary"' in result
    assert '"skills"' in result


def test_safe_render_missing_variable():
    """Отсутствующая переменная бросает ошибку"""
    template = "Привет, {name}!"
    with pytest.raises(PromptRenderingError) as exc_info:
        safe_render_prompt(template, {})
    assert "Missing prompt variables" in str(exc_info.value)
    assert "name" in str(exc_info.value)


def test_safe_render_extra_text_with_braces():
    """Текст с лишними { не ломает рендеринг"""
    template = "Используй функцию {func} или аналогичную."
    result = safe_render_prompt(template, {"func": "print"})
    assert result == "Используй функцию print или аналогичную."


def test_safe_render_list_variable():
    """Подстановка списка"""
    template = "Требования: {requirements}"
    result = safe_render_prompt(template, {"requirements": ["Python", "FastAPI"]})
    assert "Python" in result
    assert "FastAPI" in result


def test_safe_render_empty_variables():
    """Пустые переменные"""
    template = "{a}{b}{c}"
    result = safe_render_prompt(template, {"a": "1", "b": "2", "c": "3"})
    assert result == "123"
