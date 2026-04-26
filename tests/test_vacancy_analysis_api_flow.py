from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def test_vacancy_analysis_uses_profile_summary_for_scoped_match(client) -> None:
    upload_response = await client.post(
        f"{API_PREFIX}/files/upload",
        data={"file_kind": "resume"},
        files={"file": ("resume.pdf", b"%PDF-1.4 fake pdf", "application/pdf")},
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

    vacancy_response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test Company",
            "location": "Remote",
            "description_raw": (
                "Требования:\n"
                "- Python\n"
                "- FastAPI\n"
                "- PostgreSQL\n"
                "\n"
                "Будет плюсом:\n"
                "- Redis\n"
                "- Docker\n"
            ),
        },
    )
    assert vacancy_response.status_code == 200, vacancy_response.text
    vacancy_id = vacancy_response.json()["vacancy_id"]

    analysis_response = await client.post(
        f"{API_PREFIX}/vacancies/{vacancy_id}/analyze",
    )
    assert analysis_response.status_code == 200, analysis_response.text

    analysis = analysis_response.json()

    assert [item["text"] for item in analysis["must_have"]] == [
        "Python",
        "FastAPI",
        "PostgreSQL",
    ]
    assert [item["text"] for item in analysis["nice_to_have"]] == [
        "Redis",
        "Docker",
    ]

    assert analysis["keywords"] == [
        "Python",
        "FastAPI",
        "PostgreSQL",
        "Redis",
        "Docker",
    ]

    strengths_by_keyword = {item["keyword"]: item for item in analysis["strengths"]}
    gaps_by_keyword = {item["keyword"]: item for item in analysis["gaps"]}

    assert set(strengths_by_keyword) == {"Python", "FastAPI", "Docker"}
    assert set(gaps_by_keyword) == {"PostgreSQL", "Redis"}

    assert strengths_by_keyword["Python"]["scope"] == "must_have"
    assert strengths_by_keyword["FastAPI"]["scope"] == "must_have"
    assert strengths_by_keyword["Docker"]["scope"] == "nice_to_have"

    assert gaps_by_keyword["PostgreSQL"]["scope"] == "must_have"
    assert gaps_by_keyword["Redis"]["scope"] == "nice_to_have"

    assert strengths_by_keyword["Python"]["weight"] == 3
    assert strengths_by_keyword["FastAPI"]["weight"] == 3
    assert strengths_by_keyword["Docker"]["weight"] == 1

    assert gaps_by_keyword["PostgreSQL"]["weight"] == 3
    assert gaps_by_keyword["Redis"]["weight"] == 1

    assert analysis["match_score"] == 64


async def test_vacancy_import_rejects_corrupted_cyrillic_payload_via_api(client) -> None:
    response = await client.post(
        f"{API_PREFIX}/vacancies/import",
        json={
            "source": "manual",
            "title": "Backend Developer",
            "company": "Test Company",
            "location": "Remote",
            "description_raw": (
                "??????????:\n"
                "- Python\n"
                "- FastAPI\n"
                "- PostgreSQL\n"
                "\n"
                "????? ??????:\n"
                "- Redis\n"
                "- Docker\n"
            ),
        },
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == (
        "vacancy text looks corrupted; check client encoding and send JSON as UTF-8"
    )