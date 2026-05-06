"""
Тесты для PII-фильтрации в AIOrchestrator._sanitize_snapshot
"""

from __future__ import annotations

from app.ai.orchestrator import AIOrchestrator


def test_sanitize_snapshot_preserves_normal_data():
    """Обычные данные сохраняются"""
    data = {"name": "Иван", "text": "Привет, мир!"}
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["name"] == "Иван"
    assert result["text"] == "Привет, мир!"


def test_sanitize_snapshot_redacts_email():
    """Email-поля удаляются"""
    data = {"email": "user@example.com", "name": "Иван"}
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["email"] == "[REDACTED]"
    assert result["name"] == "Иван"


def test_sanitize_snapshot_redacts_phone():
    """Phone-поля удаляются"""
    data = {"phone": "+7 (999) 123-45-67", "name": "Иван"}
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["phone"] == "[REDACTED]"


def test_sanitize_snapshot_redacts_token():
    """Token-поля удаляются"""
    data = {"token": "abc123", "access_token": "xyz789", "name": "Иван"}
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["token"] == "[REDACTED]"
    assert result["access_token"] == "[REDACTED]"


def test_sanitize_snapshot_redacts_password():
    """Password-поля удаляются"""
    data = {"password": "secret123", "name": "Иван"}
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["password"] == "[REDACTED]"


def test_sanitize_snapshot_redacts_api_key():
    """API ключи удаляются"""
    data = {"api_key": "sk-abc123", "name": "Иван"}
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["api_key"] == "[REDACTED]"
    assert result["name"] == "Иван"


def test_sanitize_snapshot_redacts_secret():
    """Secret-поля удаляются"""
    data = {"secret": "supersecret", "secret_key": "key", "name": "Иван"}
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["secret"] == "[REDACTED]"
    assert result["secret_key"] == "[REDACTED]"


def test_sanitize_snapshot_truncates_long_strings():
    """Длинные строки обрезаются"""
    long_text = "x" * 3000
    data = {"text": long_text}
    result = AIOrchestrator._sanitize_snapshot(data)
    assert len(result["text"]) == 2000


def test_sanitize_snapshot_handles_nested_dict():
    """PII в вложенных словарях"""
    data = {
        "user": {
            "email": "user@example.com",
            "name": "Иван"
        }
    }
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["user"]["email"] == "[REDACTED]"
    assert result["user"]["name"] == "Иван"


def test_sanitize_snapshot_handles_nested_list():
    """PII в списках словарей"""
    data = {
        "users": [
            {"email": "a@test.com", "name": "A"},
            {"email": "b@test.com", "name": "B"}
        ]
    }
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["users"][0]["email"] == "[REDACTED]"
    assert result["users"][0]["name"] == "A"
    assert result["users"][1]["email"] == "[REDACTED]"


def test_sanitize_snapshot_case_insensitive():
    """PII-фильтрация нечувствительна к регистру"""
    data = {
        "EMAIL": "a@test.com",
        "Token": "abc",
        "API_KEY": "xyz"
    }
    result = AIOrchestrator._sanitize_snapshot(data)
    assert result["EMAIL"] == "[REDACTED]"
    assert result["Token"] == "[REDACTED]"
    assert result["API_KEY"] == "[REDACTED]"
