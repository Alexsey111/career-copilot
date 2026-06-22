from __future__ import annotations

import pytest
from httpx import AsyncClient
from uuid import UUID

from app.models import CandidateAchievement, CandidateExperience
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


@pytest.mark.asyncio
async def test_cover_letter_includes_gap_mitigation_when_needed(
    client: AsyncClient,
    db_session,
    test_user,
) -> None:
    """
    Проверяет, что при наличии gap-зон в анализе вакансии,
    сгенерированное письмо содержит проактивные формулировки.
    """
    profile_repo = CandidateProfileRepository()
    vacancy_repo = VacancyRepository()
    analysis_repo = VacancyAnalysisRepository()

    profile = await profile_repo.create_empty(db_session, user_id=test_user.id)
    profile.full_name = "Test Candidate"
    profile.headline = "Backend Engineer"
    profile.location = "Remote"
    profile.summary = "I build backend systems and keep delivery moving."
    profile.target_roles_json = ["Senior Backend Engineer"]

    experience = CandidateExperience(
        profile_id=profile.id,
        company="Acme",
        role="Backend Engineer",
        description_raw="Built backend services and supported product delivery.",
        order_index=0,
    )
    db_session.add(experience)
    await db_session.flush()

    achievement = CandidateAchievement(
        profile_id=profile.id,
        experience_id=experience.id,
        title="Built Python and FastAPI backend with PostgreSQL",
        situation="We needed a backend for a new product workflow.",
        task="Deliver a stable API with clear endpoints.",
        action="I implemented the service with Python, FastAPI and PostgreSQL.",
        result="The backend was ready for integration and review.",
        metric_text="20% faster deployments",
        evidence_note="Confirmed technical delivery in review.",
        fact_status="confirmed",
        order_index=0,
    )
    db_session.add(achievement)

    vacancy = await vacancy_repo.create(
        db_session,
        user_id=test_user.id,
        source="manual",
        source_url=None,
        external_id=None,
        title="Senior Backend Engineer",
        company="TechCorp",
        location="Remote",
        description_raw="Требуется: Python, FastAPI, PostgreSQL, Docker, Kubernetes, AWS",
        normalized_json={"requirements": ["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "AWS"]},
    )

    await analysis_repo.replace_for_vacancy(
        db_session,
        vacancy_id=vacancy.id,
        must_have_json=[
            {"text": "Python", "keyword": "python", "weight": 100},
            {"text": "FastAPI", "keyword": "fastapi", "weight": 95},
            {"text": "PostgreSQL", "keyword": "postgresql", "weight": 90},
            {"text": "Docker", "keyword": "docker", "weight": 90},
            {"text": "Kubernetes", "keyword": "kubernetes", "weight": 90},
            {"text": "AWS", "keyword": "aws", "weight": 90},
        ],
        nice_to_have_json=[],
        keywords_json=["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "AWS"],
        gaps_json=[
            {
                "keyword": "Docker",
                "scope": "must_have",
                "reason": "No confirmed Docker evidence yet",
                "requirement_text": "Docker",
                "weight": 90,
            },
            {
                "keyword": "Kubernetes",
                "scope": "must_have",
                "reason": "No confirmed Kubernetes evidence yet",
                "requirement_text": "Kubernetes",
                "weight": 90,
            },
            {
                "keyword": "AWS",
                "scope": "must_have",
                "reason": "No confirmed AWS evidence yet",
                "requirement_text": "AWS",
                "weight": 90,
            },
        ],
        strengths_json=[
            {
                "keyword": "Python",
                "scope": "must_have",
                "requirement_text": "Python",
                "evidence": "Confirmed backend work",
                "weight": 90,
            }
        ],
        match_score=84,
        analysis_version="v-test",
    )
    await db_session.commit()

    # 3. Генерация письма
    r_gen = await client.post("/api/v1/documents/letters/generate", json={"vacancy_id": str(vacancy.id)})
    assert r_gen.status_code == 200, r_gen.text
    doc_id = UUID(r_gen.json()["document_id"])

    # 4. Проверка content_json
    r_doc = await client.get(f"/api/v1/documents/{doc_id}")
    content = r_doc.json()
    rendered = content.get("rendered_text", "")

    # 5. Письмо должно содержать хотя бы одну проактивную формулировку
    mitigation_phrases = [
        "отдельно готов обсудить план быстрого погружения",
    ]
    has_mitigation = any(phrase in rendered.lower() for phrase in mitigation_phrases)
    
    # Если в анализе были gaps — ожидаем mitigation
    analysis = await client.get(f"/api/v1/vacancies/{vacancy.id}/analysis/latest")
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
