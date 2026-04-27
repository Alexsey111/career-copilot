# scripts\smoke_mvp_flow.py

from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")


RESUME_TEXT = """Алексей
Перминов
30.11.1972 г.р.

Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, Нейросети, API, SQL, FastAPI, Docker

Желаемая должность
Prompt Engineering, Data Science, Vibe-coding

ОПЫТ РАБОТЫ
Acme, AI Engineer
01.01.2023 - по настоящее время

ОБРАЗОВАНИЕ
Алтайский государственный технический университет имени И.И. Ползунова
1999 - 2001

Прошел 3 стажировки по направлению Data Science:
1. Создание ИИ-системы для мониторинга безопасности в пансионатах для пожилых
2. Автоматизированный ИИ-контроль качества ПВХ оконных изделий по изображениям и видео
3. ИИ-анализ текстовых отзывов населения
"""


VACANCY_TEXT = """Требования:
- Python
- FastAPI
- PostgreSQL

Будет плюсом:
- Redis
- Docker
"""


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def print_step(title: str, payload: dict[str, Any] | None = None) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def assert_status(response: httpx.Response, expected: int) -> None:
    if response.status_code != expected:
        raise RuntimeError(
            f"Expected HTTP {expected}, got {response.status_code}\n"
            f"URL: {response.request.method} {response.request.url}\n"
            f"Response: {response.text}"
        )


def main() -> None:
    configure_stdout()

    print_step(
        "MVP SMOKE START",
        {
            "api_base_url": API_BASE_URL,
        },
    )

    with httpx.Client(timeout=60) as client:
        # 1. Upload resume TXT
        upload_response = client.post(
            f"{API_BASE_URL}/files/upload",
            data={"file_kind": "resume"},
            files={
                "file": (
                    "resume_smoke.txt",
                    RESUME_TEXT.encode("utf-8"),
                    "text/plain; charset=utf-8",
                )
            },
        )
        assert_status(upload_response, 200)
        uploaded = upload_response.json()
        source_file_id = uploaded["id"]

        print_step(
            "1. UPLOAD RESUME",
            {
                "source_file_id": source_file_id,
                "file_kind": uploaded["file_kind"],
                "original_name": uploaded["original_name"],
            },
        )

        # 2. Import resume
        import_response = client.post(
            f"{API_BASE_URL}/profile/import-resume",
            json={"source_file_id": source_file_id},
        )
        assert_status(import_response, 200)
        imported = import_response.json()
        extraction_id = imported["extraction_id"]

        assert imported["detected_format"] == "txt"
        assert imported["text_length"] > 0

        print_step(
            "2. IMPORT RESUME",
            {
                "profile_id": imported["profile_id"],
                "extraction_id": extraction_id,
                "detected_format": imported["detected_format"],
                "text_length": imported["text_length"],
            },
        )

        # 3. Extract structured profile
        structured_response = client.post(
            f"{API_BASE_URL}/profile/extract-structured",
            json={"extraction_id": extraction_id},
        )
        assert_status(structured_response, 200)
        structured = structured_response.json()

        assert structured["profile_id"]
        assert structured["experience_count"] >= 1

        print_step(
            "3. EXTRACT STRUCTURED PROFILE",
            {
                "profile_id": structured["profile_id"],
                "full_name": structured["full_name"],
                "headline": structured["headline"],
                "target_roles": structured["target_roles"],
                "experience_count": structured["experience_count"],
                "warnings": structured["warnings"],
            },
        )

        # 4. Extract achievements
        achievements_response = client.post(
            f"{API_BASE_URL}/profile/extract-achievements",
            json={"extraction_id": extraction_id},
        )
        assert_status(achievements_response, 200)
        achievements = achievements_response.json()

        assert achievements["achievement_count"] >= 1

        print_step(
            "4. EXTRACT ACHIEVEMENTS",
            {
                "achievement_count": achievements["achievement_count"],
                "achievements": achievements["achievements"],
                "warnings": achievements["warnings"],
            },
        )

        # 5. Import vacancy
        vacancy_response = client.post(
            f"{API_BASE_URL}/vacancies/import",
            json={
                "source": "manual",
                "title": "Backend Developer",
                "company": "Test Company",
                "location": "Remote",
                "description_raw": VACANCY_TEXT,
            },
        )
        assert_status(vacancy_response, 200)
        vacancy = vacancy_response.json()
        vacancy_id = vacancy["vacancy_id"]

        assert vacancy["id"] == vacancy_id
        assert "description_raw" not in vacancy
        assert "normalized_json" not in vacancy

        print_step(
            "5. IMPORT VACANCY",
            {
                "vacancy_id": vacancy_id,
                "title": vacancy["title"],
                "description_length": vacancy["description_length"],
            },
        )

        # 6. Analyze vacancy
        analysis_response = client.post(
            f"{API_BASE_URL}/vacancies/{vacancy_id}/analyze",
        )
        assert_status(analysis_response, 200)
        analysis = analysis_response.json()

        must_have = [item["text"] for item in analysis["must_have"]]
        nice_to_have = [item["text"] for item in analysis["nice_to_have"]]
        strengths = [item["keyword"] for item in analysis["strengths"]]
        gaps = [item["keyword"] for item in analysis["gaps"]]

        assert must_have == ["Python", "FastAPI", "PostgreSQL"]
        assert nice_to_have == ["Redis", "Docker"]
        assert "Python" in strengths
        assert "FastAPI" in strengths
        assert "Docker" in strengths
        assert "PostgreSQL" in gaps
        assert "Redis" in gaps
        assert analysis["match_score"] == 64

        print_step(
            "6. ANALYZE VACANCY",
            {
                "analysis_id": analysis["analysis_id"],
                "must_have": must_have,
                "nice_to_have": nice_to_have,
                "strengths": analysis["strengths"],
                "gaps": analysis["gaps"],
                "match_score": analysis["match_score"],
            },
        )

        # 7. Generate resume
        resume_response = client.post(
            f"{API_BASE_URL}/documents/resumes/generate",
            json={"vacancy_id": vacancy_id},
        )
        assert_status(resume_response, 200)
        resume = resume_response.json()
        resume_document_id = resume["document_id"]

        assert "content_json" not in resume
        assert "rendered_text" not in resume
        assert resume["rendered_text_preview"]

        print_step(
            "7. GENERATE RESUME",
            {
                "resume_document_id": resume_document_id,
                "review_status": resume["review_status"],
                "version_label": resume["version_label"],
                "preview_start": resume["rendered_text_preview"][:300],
            },
        )

        # 8. Generate cover letter
        letter_response = client.post(
            f"{API_BASE_URL}/documents/letters/generate",
            json={"vacancy_id": vacancy_id},
        )
        assert_status(letter_response, 200)
        letter = letter_response.json()
        cover_letter_document_id = letter["document_id"]

        assert "content_json" not in letter
        assert "rendered_text" not in letter
        assert letter["rendered_text_preview"]

        print_step(
            "8. GENERATE COVER LETTER",
            {
                "cover_letter_document_id": cover_letter_document_id,
                "review_status": letter["review_status"],
                "version_label": letter["version_label"],
                "preview_start": letter["rendered_text_preview"][:300],
            },
        )

        # 9. Approve resume
        approve_resume_response = client.patch(
            f"{API_BASE_URL}/documents/{resume_document_id}/review",
            json={
                "review_status": "approved",
                "review_comment": "approved by smoke script",
                "set_active_when_approved": True,
            },
        )
        assert_status(approve_resume_response, 200)
        approved_resume = approve_resume_response.json()

        assert approved_resume["is_active"] is True
        assert approved_resume["review_status"] == "approved"

        print_step(
            "9. APPROVE RESUME",
            {
                "document_id": approved_resume["document_id"],
                "is_active": approved_resume["is_active"],
                "review_status": approved_resume["review_status"],
            },
        )

        # 10. Approve cover letter
        approve_letter_response = client.patch(
            f"{API_BASE_URL}/documents/{cover_letter_document_id}/review",
            json={
                "review_status": "approved",
                "review_comment": "approved by smoke script",
                "set_active_when_approved": True,
            },
        )
        assert_status(approve_letter_response, 200)
        approved_letter = approve_letter_response.json()

        assert approved_letter["is_active"] is True
        assert approved_letter["review_status"] == "approved"

        print_step(
            "10. APPROVE COVER LETTER",
            {
                "document_id": approved_letter["document_id"],
                "is_active": approved_letter["is_active"],
                "review_status": approved_letter["review_status"],
            },
        )

        # 11. Create application
        application_response = client.post(
            f"{API_BASE_URL}/applications",
            json={
                "vacancy_id": vacancy_id,
                "notes": "Created by MVP smoke script",
            },
        )
        assert_status(application_response, 200)
        application = application_response.json()
        application_id = application["id"]

        assert application["status"] == "draft"
        assert application["resume_document_id"] == resume_document_id
        assert application["cover_letter_document_id"] == cover_letter_document_id

        print_step(
            "11. CREATE APPLICATION",
            {
                "application_id": application_id,
                "status": application["status"],
                "resume_document_id": application["resume_document_id"],
                "cover_letter_document_id": application["cover_letter_document_id"],
            },
        )

        # 12. Duplicate application protection
        duplicate_response = client.post(
            f"{API_BASE_URL}/applications",
            json={
                "vacancy_id": vacancy_id,
                "notes": "Duplicate should fail",
            },
        )
        assert_status(duplicate_response, 409)

        print_step(
            "12. DUPLICATE APPLICATION PROTECTION",
            {
                "status_code": duplicate_response.status_code,
                "detail": duplicate_response.json()["detail"],
            },
        )

        # 13. Update application status
        submitted_response = client.patch(
            f"{API_BASE_URL}/applications/{application_id}/status",
            json={
                "status": "submitted",
                "notes": "Submitted manually on HH",
            },
        )
        assert_status(submitted_response, 200)
        submitted = submitted_response.json()

        assert submitted["status"] == "submitted"
        assert submitted["applied_at"] is not None

        print_step(
            "13. UPDATE APPLICATION STATUS",
            {
                "application_id": submitted["id"],
                "status": submitted["status"],
                "applied_at": submitted["applied_at"],
                "notes": submitted["notes"],
            },
        )

        # 14. Create interview session
        interview_response = client.post(
            f"{API_BASE_URL}/interviews/sessions",
            json={
                "vacancy_id": vacancy_id,
                "session_type": "vacancy",
            },
        )
        assert_status(interview_response, 200)
        interview = interview_response.json()
        interview_session_id = interview["id"]

        assert interview["status"] == "draft"
        assert interview["question_set"]

        question_types = {item["type"] for item in interview["question_set"]}
        assert "role_overview" in question_types
        assert "must_have_requirement" in question_types
        assert "gap_preparation" in question_types
        assert "strength_deep_dive" in question_types
        assert "achievement_star_story" in question_types

        print_step(
            "14. CREATE INTERVIEW SESSION",
            {
                "interview_session_id": interview_session_id,
                "status": interview["status"],
                "question_count": len(interview["question_set"]),
                "question_types": sorted(question_types),
            },
        )

        # 15. Submit interview answers
        answers_response = client.patch(
            f"{API_BASE_URL}/interviews/sessions/{interview_session_id}/answers",
            json={
                "answers": [
                    {
                        "question_index": 0,
                        "answer_text": (
                            "I am interested in this role because it matches my Python "
                            "and backend development direction."
                        ),
                    },
                    {
                        "question_index": 1,
                        "answer_text": (
                            "Situation: I worked on a practical Python project. "
                            "Task: build a working prototype. "
                            "Action: I implemented the backend flow. "
                            "Result: the prototype was ready for review."
                        ),
                    },
                ]
            },
        )
        assert_status(answers_response, 200)
        answered = answers_response.json()

        assert answered["status"] == "answered"
        assert len(answered["answers"]) == 2
        assert answered["feedback"]["feedback_version"] == "deterministic_v1"
        assert answered["score"]["score_version"] == "deterministic_v2"
        assert answered["score"]["question_count"] >= 1
        assert answered["score"]["answered_count"] == 2
        assert answered["score"]["unanswered_count"] >= 0
        assert answered["score"]["readiness_score"] is not None

        print_step(
            "15. SUBMIT INTERVIEW ANSWERS",
            {
                "interview_session_id": answered["id"],
                "status": answered["status"],
                "answer_count": len(answered["answers"]),
                "feedback": answered["feedback"],
                "score": answered["score"],
            },
        )

    print_step(
        "MVP SMOKE PASSED",
        {
            "source_file_id": source_file_id,
            "extraction_id": extraction_id,
            "vacancy_id": vacancy_id,
            "analysis_id": analysis["analysis_id"],
            "resume_document_id": resume_document_id,
            "cover_letter_document_id": cover_letter_document_id,
            "application_id": application_id,
            "interview_session_id": interview_session_id,
        },
    )


if __name__ == "__main__":
    main()
