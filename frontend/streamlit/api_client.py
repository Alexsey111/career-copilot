# frontend\streamlit\api_client.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1"


@dataclass(frozen=True)
class BackendCheckResult:
    ok: bool
    status_code: int | None
    app_title: str | None
    api_version: str | None
    path_count: int | None
    error: str | None = None


class CareerCopilotApiClient:
    def __init__(
        self,
        api_base_url: str = DEFAULT_API_BASE_URL,
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def api_root_url(self) -> str:
        if self.api_base_url.endswith("/api/v1"):
            return self.api_base_url[: -len("/api/v1")]
        if "/api/" in self.api_base_url:
            return self.api_base_url.split("/api/", 1)[0]
        return self.api_base_url

    def check_backend(self) -> BackendCheckResult:
        url = f"{self.api_root_url}/health"

        try:
            response = httpx.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            return BackendCheckResult(
                ok=False,
                status_code=exc.response.status_code,
                app_title=None,
                api_version=None,
                path_count=None,
                error=f"Backend returned HTTP {exc.response.status_code}",
            )
        except httpx.RequestError as exc:
            return BackendCheckResult(
                ok=False,
                status_code=None,
                app_title=None,
                api_version=None,
                path_count=None,
                error=f"Cannot connect to backend: {exc}",
            )
        except ValueError as exc:
            return BackendCheckResult(
                ok=False,
                status_code=response.status_code if "response" in locals() else None,
                app_title=None,
                api_version=None,
                path_count=None,
                error=f"Backend response is not valid JSON: {exc}",
            )

        return BackendCheckResult(
            ok=True,
            status_code=response.status_code,
            app_title=str(payload.get("status") or "ok"),
            api_version=None,
            path_count=None,
            error=None,
        )

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Вход через JSON-контракт: {"email": "...", "password": "..."}"""
        payload = {"email": email, "password": password}
        response = httpx.post(
            self._build_url("/auth/login"),
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        result = response.json()
        # Нормализуем ответ под единый ключ
        if "access_token" not in result and "token" in result:
            result["access_token"] = result["token"]
        return result

    def register(self, email: str, password: str) -> dict[str, Any]:
        payload = {"email": email, "password": password}
        response = httpx.post(
            self._build_url("/auth/register"),
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Expected JSON object from register endpoint")
        return result

    def import_vacancy_from_url(
        self,
        *,
        source_url: str,
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.post_json(
            "/vacancies/import-from-url",
            {"source_url": source_url},
            token=token,
            timeout_seconds=max(self.timeout_seconds, 45.0),
        )

    def intake_manual_profile(
        self,
        payload: dict[str, Any],
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.post_json("/profile/intake/manual", payload, token=token)

    def intake_github_profile(
        self,
        payload: dict[str, Any],
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.post_json("/profile/intake/github", payload, token=token)

    def import_github_public_profile(
        self,
        *,
        profile_url: str,
        target_role: str | None = None,
        max_repositories: int = 12,
        include_readme: bool = True,
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.post_json(
            "/profile/intake/github-public",
            {
                "profile_url": profile_url,
                "target_role": target_role,
                "max_repositories": max_repositories,
                "include_readme": include_readme,
            },
            token=token,
            timeout_seconds=max(self.timeout_seconds, 90.0),
        )

    def get_active_resume_source(self, token: str | None = None) -> dict[str, Any] | None:
        return self.get_json("/files/resume/active", token=token)

    def _build_headers(self, token: str | None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def get_json(self, path: str, token: str | None = None) -> Any:
        response = httpx.get(
            self._build_url(path),
            headers=self._build_headers(token),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def get_document_version(self, document_id: str, token: str | None = None) -> dict[str, Any]:
        return self.get_json(f"/documents/{document_id}", token=token)

    def get_active_document(
        self,
        *,
        document_kind: str,
        vacancy_id: str | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        path = f"/documents/active?document_kind={document_kind}"
        if vacancy_id:
            path = f"{path}&vacancy_id={vacancy_id}"
        return self.get_json(path, token=token)

    def get_document_diff(
        self,
        *,
        base_document_id: str,
        target_document_id: str,
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.get_json(
            f"/documents/{base_document_id}/diff/{target_document_id}",
            token=token,
        )

    def get_text(self, path: str, token: str | None = None) -> str:
        response = httpx.get(
            self._build_url(path),
            headers=self._build_headers(token),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.text

    def get_bytes(self, path: str, token: str | None = None) -> bytes:
        response = httpx.get(
            self._build_url(path),
            headers=self._build_headers(token),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.content

    def post_json(
        self,
        path: str,
        payload: dict[str, Any],
        token: str | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        response = httpx.post(
            self._build_url(path),
            json=payload,
            headers=self._build_headers(token),
            timeout=timeout_seconds or self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def patch_json(self, path: str, payload: dict[str, Any], token: str | None = None) -> Any:
        response = httpx.patch(
            self._build_url(path),
            json=payload,
            headers=self._build_headers(token),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def get_application_analytics_summary(self, token: str | None = None) -> dict[str, Any]:
        return self.get_json("/applications/analytics/summary", token=token)

    def get_application_reminders(self, token: str | None = None) -> list[Any]:
        return self.get_json("/applications/reminders", token=token)

    def get_system_health_diagnostics(self, token: str | None = None) -> dict[str, Any]:
        return self.get_json("/health/diagnostics", token=token)

    def get_document_review_summary(self, document_id: str, token: str | None = None) -> dict[str, Any]:
        return self.get_review_summary(
            entity_type="document",
            entity_id=document_id,
            token=token,
        )

    def get_review_summary(
        self,
        *,
        entity_type: str,
        entity_id: str,
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.get_json(f"/review/summary/{entity_type}/{entity_id}", token=token)

    def list_evidence_snippets(self, token: str | None = None) -> list[Any]:
        return self.get_json("/evidence/snippets", token=token)

    def get_evidence_snippet(
        self,
        snippet_id: str,
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.get_json(f"/evidence/snippets/{snippet_id}", token=token)

    def list_evidence_usages(self, token: str | None = None) -> list[Any]:
        return self.get_json("/evidence/usages", token=token)

    def get_evidence_insights(self, token: str | None = None) -> dict[str, Any]:
        return self.get_json("/evidence/insights", token=token)

    def list_interview_prep_sessions(self, token: str | None = None) -> list[Any]:
        return self.get_json("/interview-prep/sessions", token=token)

    def create_interview_prep_session(
        self,
        *,
        application_id: str,
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.post_json(
            "/interview-prep/sessions",
            {"application_id": application_id},
            token=token,
        )

    def get_interview_prep_session(
        self,
        session_id: str,
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.get_json(f"/interview-prep/sessions/{session_id}", token=token)

    def get_interview_prep_readiness(
        self,
        session_id: str,
        token: str | None = None,
    ) -> dict[str, Any]:
        return self.get_json(f"/interview-prep/sessions/{session_id}/readiness", token=token)

    def match_vacancy(self, vacancy_id: str, token: str | None = None) -> dict[str, Any]:
        """
        Запускает match-анализ вакансии с профилем текущего пользователя.
        Возвращает: match_score, strengths, gaps, analysis_version.
        """
        return self.post_json(
            f"/vacancies/{vacancy_id}/match",
            {},  # пустой payload, user_id берётся из сессии на бэкенде
            token=token,
        )

    def get_vacancy_fit(self, vacancy_id: str, token: str | None = None) -> dict[str, Any]:
        return self.get_json(f"/vacancies/{vacancy_id}/fit", token=token)

    def get_career_insights(self, token: str | None = None) -> dict[str, Any]:
        return self.get_json("/career-insights/summary", token=token)

    def upload_file(
        self,
        *,
        path: str,
        file_kind: str,
        filename: str,
        content: bytes,
        content_type: str,
        token: str | None = None,
    ) -> dict[str, Any]:
        headers = self._build_headers(token)
        headers.pop("Content-Type", None)  # httpx сам выставит multipart boundary
        response = httpx.post(
            self._build_url(path),
            data={"file_kind": file_kind},
            files={"file": (filename, content, content_type)},
            headers=headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Expected JSON object from file upload endpoint")
        return payload

    def _build_url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self.api_base_url}{normalized_path}"
