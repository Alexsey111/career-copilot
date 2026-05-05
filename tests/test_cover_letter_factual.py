from __future__ import annotations

import pytest
from httpx import AsyncClient
from uuid import UUID


@pytest.mark.asyncio
async def test_cover_letter_includes_gap_mitigation_when_needed(
    client: AsyncClient,
    db_session,
) -> None:
    """
    Проверяет, что при наличии gap-зон в анализе вакансии,
    сгенерированное письмо содержит проактивные формулировки.
    """
    # 0. Профиль (обязательно)
    upload = await client.post("/api/v1/files/upload", data={"file_kind": "resume"}, files={"file": ("r.pdf", b"%PDF", "application/pdf")})
    assert upload.status_code == 200
    source_id = upload.json()["id"]
    
    imp = await client.post("/api/v1/profile/import-resume", json={"source_file_id": source_id})
    ext_id = imp.json()["extraction_id"]
    await client.post("/api/v1/profile/extract-structured", json={"extraction_id": ext_id})
    await client.post("/api/v1/profile/extract-achievements", json={"extraction_id": ext_id})

    # 1. Вакансия с явными gap'ами
    vacancy_payload = {
        "source": "manual",
        "title": "Senior Backend Engineer",
        "company": "TechCorp",
        "description_raw": "Требуется: Python, FastAPI, PostgreSQL, Docker, Kubernetes, AWS",
    }
    r_vac = await client.post("/api/v1/vacancies/import", json=vacancy_payload)
    vacancy_id = UUID(r_vac.json()["vacancy_id"])

    # 2. Анализ
    await client.post(f"/api/v1/vacancies/{vacancy_id}/analyze")

    # 3. Генерация письма
    r_gen = await client.post("/api/v1/documents/letters/generate", json={"vacancy_id": str(vacancy_id)})
    assert r_gen.status_code == 200
    doc_id = UUID(r_gen.json()["document_id"])

    # 4. Проверка content_json
    r_doc = await client.get(f"/api/v1/documents/{doc_id}")
    content = r_doc.json()
    rendered = content.get("rendered_text", "")

    # 5. Письмо должно содержать хотя бы одну проактивную формулировку
    mitigation_phrases = [
        "готов быстро адаптироваться",
        "активно изучаю",
        "готов оперативно закрыть",
        "готов углубить",
    ]
    has_mitigation = any(phrase in rendered.lower() for phrase in mitigation_phrases)
    
    # Если в анализе были gaps — ожидаем mitigation
    analysis = await client.get(f"/api/v1/vacancies/{vacancy_id}/analysis/latest")
    gaps = analysis.json().get("gaps", [])
    if gaps:
        assert has_mitigation, (
            f"Письмо должно содержать проактивные формулировки для закрытия пробелов. "
            f"Gap'ы: {[g.get('keyword') for g in gaps]}. Текст письма:\n{rendered}"
        )


@pytest.mark.asyncio
async def test_cover_letter_does_not_duplicate_resume_content(
    client: AsyncClient,
    db_session,
) -> None:
    """
    Проверяет, что письмо не копирует резюме дословно,
    а добавляет мотивацию и контекст.
    """
    # Минимальный сценарий: профиль + вакансия → письмо
    upload = await client.post("/api/v1/files/upload", data={"file_kind": "resume"}, files={"file": ("r.pdf", b"%PDF", "application/pdf")})
    source_id = upload.json()["id"]
    
    imp = await client.post("/api/v1/profile/import-resume", json={"source_file_id": source_id})
    ext_id = imp.json()["extraction_id"]
    await client.post("/api/v1/profile/extract-structured", json={"extraction_id": ext_id})
    await client.post("/api/v1/profile/extract-achievements", json={"extraction_id": ext_id})

    vacancy_payload = {
        "source": "manual",
        "title": "Python Developer",
        "description_raw": "Требуется: Python, Git, API",
    }
    r_vac = await client.post("/api/v1/vacancies/import", json=vacancy_payload)
    vacancy_id = UUID(r_vac.json()["vacancy_id"])

    await client.post(f"/api/v1/vacancies/{vacancy_id}/analyze")

    # Генерируем и резюме, и письмо
    r_resume = await client.post("/api/v1/documents/resumes/generate", json={"vacancy_id": str(vacancy_id)})
    r_letter = await client.post("/api/v1/documents/letters/generate", json={"vacancy_id": str(vacancy_id)})

    resume_doc = await client.get(f"/api/v1/documents/{r_resume.json()['document_id']}")
    letter_doc = await client.get(f"/api/v1/documents/{r_letter.json()['document_id']}")

    resume_text = resume_doc.json().get("rendered_text", "")
    letter_text = letter_doc.json().get("rendered_text", "")

    # Письмо должно быть короче и содержать мотивационные маркеры
    assert "Здравствуйте" in letter_text
    assert "буду рад обсудить" in letter_text.lower() or "хочу обсудить" in letter_text.lower()
    
    # Письмо не должно быть точной копией резюме
    assert letter_text.strip() != resume_text.strip()