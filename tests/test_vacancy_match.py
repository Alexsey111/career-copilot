from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_vacancy_match_flow(
    client: AsyncClient,
) -> None:
    # ---------------------------------------------------------
    # login / register test user
    # ---------------------------------------------------------
    email = f"match-{uuid.uuid4()}@example.com"
    password = "StrongPass123!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code in (200, 201), register_response.text

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # ---------------------------------------------------------
    # upload file and create profile
    # ---------------------------------------------------------
    upload_response = await client.post(
        "/api/v1/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf\n", "application/pdf")},
        headers=headers,
    )
    assert upload_response.status_code == 200, upload_response.text
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        "/api/v1/profile/import-resume",
        json={"source_file_id": source_file_id},
        headers=headers,
    )
    assert import_response.status_code == 200, import_response.text
    extraction_id = import_response.json()["extraction_id"]

    structured_response = await client.post(
        "/api/v1/profile/extract-structured",
        json={"extraction_id": extraction_id},
        headers=headers,
    )
    assert structured_response.status_code == 200, structured_response.text

    achievements_response = await client.post(
        "/api/v1/profile/extract-achievements",
        json={"extraction_id": extraction_id},
        headers=headers,
    )
    assert achievements_response.status_code == 200, achievements_response.text

    # ---------------------------------------------------------
    # create vacancy
    # ---------------------------------------------------------
    vacancy_payload = {
        "source": "manual",
        "title": "Senior Python Backend Engineer",
        "company": "TechCorp",
        "location": "Remote",
        "description_raw": (
            "Требования\n"
            "- Python\n"
            "- FastAPI\n"
            "- PostgreSQL\n"
            "- Docker\n\n"
            "Будет плюсом\n"
            "- CI/CD\n"
        ),
    }

    vacancy_response = await client.post(
        "/api/v1/vacancies/import",
        json=vacancy_payload,
        headers=headers,
    )

    assert vacancy_response.status_code in (200, 201), vacancy_response.text

    vacancy_id = vacancy_response.json()["vacancy_id"]

    # ---------------------------------------------------------
    # analyze
    # ---------------------------------------------------------
    analyze_response = await client.post(
        f"/api/v1/vacancies/{vacancy_id}/analyze",
        headers=headers,
    )

    assert analyze_response.status_code == 200, analyze_response.text

    # ---------------------------------------------------------
    # match
    # ---------------------------------------------------------
    match_response = await client.post(
        f"/api/v1/vacancies/{vacancy_id}/match",
        headers=headers,
    )

    assert match_response.status_code == 200, match_response.text

    payload = match_response.json()
    # 1. Базовые контракты
    assert payload["vacancy_id"] == str(vacancy_id)
    assert payload["analysis_version"] == "deterministic_match_v1"
    # 2. Валидация скоринга
    score = payload["match_score"]
    assert isinstance(score, int)
    assert 0 <= score <= 100, f"match_score должен быть в диапазоне 0-100, получено: {score}"
    # 3. Структурная проверка strengths / gaps
    strengths = payload["strengths"]
    gaps = payload["gaps"]
    assert isinstance(strengths, list) and isinstance(gaps, list)
    for s in strengths:
        assert isinstance(s, dict)
        assert "keyword" in s, "strengths должен содержать 'keyword'"
        assert "scope" in s, "strengths должен содержать 'scope'"
        assert "weight" in s, "strengths должен содержать 'weight'"
    for g in gaps:
        assert isinstance(g, dict)
        assert "keyword" in g, "gaps должен содержать 'keyword'"
        assert "reason" in g, "gaps должен содержать 'reason'"
    # 4. Логика покрытия: хотя бы часть требований обработана
    total_processed = len(strengths) + len(gaps)
    assert total_processed > 0, "match должен вернуть минимум один strength или gap"
    # 5. Семантическая проверка (гибкая, т.к. профиль генерируется из мок-PDF)
    all_keywords = [s.get("keyword") for s in strengths] + [g.get("keyword") for g in gaps]
    # Python точно есть в описании вакансии → обязан попасть в strengths или gaps
    assert any("python" in k.lower() for k in all_keywords), \
        "Ключевое слово 'Python' из вакансии должно присутствовать в strengths или gaps"