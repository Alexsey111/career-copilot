from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def _extract_achievement(client) -> dict:
    resume_text = """
Перминов Алексей
Профессиональные навыки
Python, FastAPI, Docker

ПРОЕКТЫ
1. Создание ИИ-системы для мониторинга безопасности в пансионатах для пожилых

ОБРАЗОВАНИЕ
Тестовое образование
""".encode("utf-8")

    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.txt", resume_text, "text/plain")},
    )
    assert upload_response.status_code == 200, upload_response.text
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        f"{API_PREFIX}/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert import_response.status_code == 200, import_response.text
    extraction_id = import_response.json()["extraction_id"]

    structured_response = await client.post(
        f"{API_PREFIX}/profile/extract-structured",
        json={"extraction_id": extraction_id},
    )
    assert structured_response.status_code == 200, structured_response.text

    achievements_response = await client.post(
        f"{API_PREFIX}/profile/extract-achievements",
        json={"extraction_id": extraction_id},
    )
    assert achievements_response.status_code == 200, achievements_response.text

    achievements = achievements_response.json()["achievements"]
    assert achievements

    return achievements[0]


async def test_achievement_review_saves_star_metric_and_evidence_fields(client) -> None:
    achievement = await _extract_achievement(client)

    response = await client.patch(
        f"{API_PREFIX}/profile/achievements/{achievement['id']}/review",
        json={
            "title": achievement["title"],
            "situation": "В пансионатах нужно было быстрее замечать потенциально опасные ситуации.",
            "task": "Собрать прототип ИИ-мониторинга по изображениям.",
            "action": "Я подготовил логику анализа изображений и сценарий проверки результата.",
            "result": "Получился прототип для дальнейшей проверки на реальных данных.",
            "metric_text": "метрика требует отдельного подтверждения",
            "fact_status": "confirmed",
            "evidence_note": "Подтверждено пользователем в тестовом review flow.",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["id"] == achievement["id"]
    assert payload["title"] == achievement["title"]
    assert payload["situation"].startswith("В пансионатах")
    assert payload["task"].startswith("Собрать прототип")
    assert payload["action"].startswith("Я подготовил")
    assert payload["result"].startswith("Получился прототип")
    assert payload["metric_text"] == "метрика требует отдельного подтверждения"
    assert payload["fact_status"] == "confirmed"
    assert payload["evidence_note"] == "Подтверждено пользователем в тестовом review flow."
    assert payload["updated_at"] is not None