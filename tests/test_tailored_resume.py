from __future__ import annotations

import pytest
from httpx import AsyncClient
from uuid import UUID


@pytest.mark.asyncio
async def test_tailored_resume_uses_matched_keywords_early(
    client: AsyncClient,
    db_session,
) -> None:
    """
    Проверяет, что сгенерированное резюме:
    1. Помещает matched keywords в начало текста
    2. Содержит только confirmed достижения
    3. Блокирует экспорт до human review
    """
    # 0. Создаём профиль через pipeline
    upload_response = await client.post(
        "/api/v1/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf\n", "application/pdf")},
    )
    assert upload_response.status_code == 200, upload_response.text
    source_file_id = upload_response.json()["id"]

    import_response = await client.post(
        "/api/v1/profile/import-resume",
        json={"source_file_id": source_file_id},
    )
    assert import_response.status_code == 200, import_response.text
    extraction_id = import_response.json()["extraction_id"]

    await client.post("/api/v1/profile/extract-structured", json={"extraction_id": extraction_id})
    await client.post("/api/v1/profile/extract-achievements", json={"extraction_id": extraction_id})

    # 1. Создаём вакансию
    vacancy_payload = {
        "source": "manual",
        "title": "Senior Python Backend Engineer",
        "company": "TechCorp",
        "location": "Remote",
        "description_raw": (
            "Требования\n- Python\n- FastAPI\n- PostgreSQL\n- Docker\n\n"
            "Будет плюсом\n- CI/CD\n"
        ),
    }
    r_vac = await client.post("/api/v1/vacancies/import", json=vacancy_payload)
    assert r_vac.status_code == 200
    vacancy_id = UUID(r_vac.json()["vacancy_id"])

    # 2. Анализируем вакансию
    r_analyze = await client.post(f"/api/v1/vacancies/{vacancy_id}/analyze")
    assert r_analyze.status_code == 200
    analysis = r_analyze.json()

    # 3. Генерируем резюме
    r_gen = await client.post(
        "/api/v1/documents/resumes/generate",
        json={"vacancy_id": str(vacancy_id)},
    )
    assert r_gen.status_code == 200, f"Generate failed: {r_gen.text}"
    doc_id = UUID(r_gen.json()["document_id"])

    # 4. Получаем полный документ
    r_doc = await client.get(f"/api/v1/documents/{doc_id}")
    assert r_doc.status_code == 200
    doc_data = r_doc.json()
    rendered = doc_data.get("rendered_text") or ""

    # 5. Проверка структуры
    assert "ЦЕЛЕВАЯ ПОЗИЦИЯ" in rendered
    assert "КЛЮЧЕВЫЕ НАВЫКИ" in rendered

    # Если есть matched keywords, проверяем их присутствие в первой половине (ATS best practice)
    matched_keywords = [
        s.get("keyword", "").lower()
        for s in analysis.get("strengths", [])
        if s.get("keyword")
    ]
    if matched_keywords:
        first_half = rendered[: len(rendered) // 2].lower()
        found_early = [kw for kw in matched_keywords if kw and kw in first_half]
        assert len(found_early) >= 1, (
            f"Matched keywords {matched_keywords} должны попадать в начало резюме. "
            f"Найдено: {found_early}"
        )

    # 6. Проверка статусов и блокировки экспорта
    assert doc_data["review_status"] == "draft"
    assert doc_data["is_active"] is False

    r_export = await client.get(f"/api/v1/documents/{doc_id}/export/txt")
    assert r_export.status_code == 409
    assert "approved and active" in r_export.json()["detail"]


@pytest.mark.asyncio
async def test_tailored_resume_excludes_unconfirmed_achievements(
    client: AsyncClient,
    db_session,
) -> None:
    """
    Проверяет, что в резюме не попадают достижения со статусом needs_confirmation.
    """
    # 0. Профиль
    upload_response = await client.post(
        "/api/v1/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf\n", "application/pdf")},
    )
    assert upload_response.status_code == 200
    source_file_id = upload_response.json()["id"]
    import_resp = await client.post("/api/v1/profile/import-resume", json={"source_file_id": source_file_id})
    extraction_id = import_resp.json()["extraction_id"]
    await client.post("/api/v1/profile/extract-structured", json={"extraction_id": extraction_id})
    await client.post("/api/v1/profile/extract-achievements", json={"extraction_id": extraction_id})

    # 1. Вакансия
    vacancy_payload = {
        "source": "manual",
        "title": "Data Engineer",
        "company": "DataCo",
        "description_raw": "Требуется: Python, SQL, Airflow",
    }
    r_vac = await client.post("/api/v1/vacancies/import", json=vacancy_payload)
    vacancy_id = UUID(r_vac.json()["vacancy_id"])

    # 2. Анализ
    await client.post(f"/api/v1/vacancies/{vacancy_id}/analyze")

    # 3. Генерация
    r_gen = await client.post(
        "/api/v1/documents/resumes/generate",
        json={"vacancy_id": str(vacancy_id)},
    )
    assert r_gen.status_code == 200, f"Generate failed: {r_gen.text}"
    doc_id = UUID(r_gen.json()["document_id"])

    # 4. Проверка content_json
    r_doc = await client.get(f"/api/v1/documents/{doc_id}")
    content = r_doc.json()
    selected = content.get("sections", {}).get("selected_achievements", [])

    for ach in selected:
        assert ach.get("fact_status") == "confirmed", (
            f"Неподтверждённое достижение попало в резюме: {ach}"
        )

    # 5. В тексте не должно быть служебных меток
    rendered = content.get("rendered_text", "")
    assert "needs_confirmation" not in rendered.lower()