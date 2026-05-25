from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio

API_PREFIX = "/api/v1"


async def test_vacancy_import_from_url_uses_hh_mapping(client, monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_fetch_vacancy(
        self,
        source_url: str,
        *,
        contact_email: str | None = None,
    ) -> dict[str, object]:
        captured["source_url"] = source_url
        captured["contact_email"] = contact_email
        return {
            "id": 12345678,
            "name": "Senior Python Backend Engineer",
            "description": "<p>Build APIs</p>",
            "employer": {"name": "TechCorp"},
            "area": {"name": "Remote"},
            "key_skills": [{"name": "Python"}, {"name": "FastAPI"}],
            "experience": {"name": "3-6 years"},
            "employment": {"name": "Full-time"},
            "schedule": {"name": "Remote"},
        }

    def fake_map_to_import_payload(
        self,
        payload: dict[str, object],
        *,
        source_url: str,
    ) -> dict[str, object]:
        captured["mapped_source_url"] = source_url
        captured["mapped_payload_id"] = payload["id"]
        return {
            "source": "hh",
            "source_url": source_url,
            "external_id": str(payload["id"]),
            "title": payload["name"],
            "company": payload["employer"]["name"],
            "location": payload["area"]["name"],
            "description_raw": "Mapped HH vacancy text",
        }

    monkeypatch.setattr(
        "app.api.routes.vacancies.HHVacancyImportService.fetch_vacancy",
        fake_fetch_vacancy,
    )
    monkeypatch.setattr(
        "app.api.routes.vacancies.HHVacancyImportService.map_to_import_payload",
        fake_map_to_import_payload,
    )

    response = await client.post(
        f"{API_PREFIX}/vacancies/import-from-url",
        json={"source_url": "https://hh.ru/vacancy/12345678"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert captured["source_url"] == "https://hh.ru/vacancy/12345678"
    assert str(captured["contact_email"]).endswith("@local.test")
    assert captured["mapped_source_url"] == "https://hh.ru/vacancy/12345678"
    assert captured["mapped_payload_id"] == 12345678
    assert payload["source"] == "hh"
    assert payload["source_url"] == "https://hh.ru/vacancy/12345678"
    assert payload["title"] == "Senior Python Backend Engineer"
    assert payload["company"] == "TechCorp"
    assert payload["location"] == "Remote"
    assert payload["description_length"] == len("Mapped HH vacancy text")
