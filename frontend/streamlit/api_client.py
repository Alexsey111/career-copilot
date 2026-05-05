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
        url = f"{self.api_root_url}/openapi.json"

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

        paths = payload.get("paths")
        info = payload.get("info", {})

        return BackendCheckResult(
            ok=True,
            status_code=response.status_code,
            app_title=info.get("title"),
            api_version=info.get("version"),
            path_count=len(paths) if isinstance(paths, dict) else None,
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

    def post_json(self, path: str, payload: dict[str, Any], token: str | None = None) -> Any:
        response = httpx.post(
            self._build_url(path),
            json=payload,
            headers=self._build_headers(token),
            timeout=self.timeout_seconds,
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
