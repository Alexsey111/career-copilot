from __future__ import annotations

import pytest

from frontend.streamlit.api_client import CareerCopilotApiClient


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_register_returns_json_object(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "access_token": "token-123",
                "refresh_token": "refresh-123",
                "token_type": "bearer",
            }
        )

    monkeypatch.setattr("httpx.post", fake_post)

    client = CareerCopilotApiClient(api_base_url="http://localhost:8000/api/v1", timeout_seconds=7.5)
    result = client.register("new.user@example.com", "StrongPass123!")

    assert captured["url"] == "http://localhost:8000/api/v1/auth/register"
    assert captured["json"] == {
        "email": "new.user@example.com",
        "password": "StrongPass123!",
    }
    assert captured["timeout"] == 7.5
    assert result["access_token"] == "token-123"
    assert result["refresh_token"] == "refresh-123"
    assert result["token_type"] == "bearer"


def test_register_rejects_non_object_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url, json, timeout):
        return _FakeResponse(["unexpected", "payload"])

    monkeypatch.setattr("httpx.post", fake_post)

    client = CareerCopilotApiClient(api_base_url="http://localhost:8000/api/v1")

    with pytest.raises(ValueError, match="Expected JSON object from register endpoint"):
        client.register("new.user@example.com", "StrongPass123!")


def test_import_vacancy_from_url_posts_to_hh_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "id": "vacancy-id",
                "source": "hh",
                "source_url": "https://hh.ru/vacancy/123",
            }
        )

    monkeypatch.setattr("httpx.post", fake_post)

    client = CareerCopilotApiClient(api_base_url="http://localhost:8000/api/v1", timeout_seconds=4.0)
    result = client.import_vacancy_from_url(
        source_url="https://hh.ru/vacancy/123",
        token="token-abc",
    )

    assert captured["url"] == "http://localhost:8000/api/v1/vacancies/import-from-url"
    assert captured["json"] == {"source_url": "https://hh.ru/vacancy/123"}
    assert captured["headers"]["Authorization"] == "Bearer token-abc"
    assert captured["timeout"] == 45.0
    assert result["source"] == "hh"


def test_review_summary_rejects_missing_entity_id_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(*args, **kwargs):
        raise AssertionError("HTTP request should not be made for missing entity_id")

    monkeypatch.setattr("httpx.get", fake_get)

    client = CareerCopilotApiClient(api_base_url="http://localhost:8000/api/v1")

    with pytest.raises(ValueError, match="review summary entity_id is required"):
        client.get_document_review_summary(None)

    with pytest.raises(ValueError, match="review summary entity_id is required"):
        client.get_document_review_summary("None")

    with pytest.raises(ValueError, match="review summary entity_id is required"):
        client.get_review_summary(entity_type="document", entity_id="None")
