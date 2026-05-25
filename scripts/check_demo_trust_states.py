from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.streamlit.api_client import CareerCopilotApiClient, DEFAULT_API_BASE_URL


API_BASE_URL = os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL)
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo.candidate@example.com")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "DemoPass123!")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _print_summary(title: str, payload: dict[str, Any]) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)
    print(
        {
            "entity_type": payload.get("entity_type"),
            "entity_id": payload.get("entity_id"),
            "ready": payload.get("ready"),
            "risk_level": payload.get("risk_level"),
            "requires_human_review": payload.get("requires_human_review"),
            "confidence_level": (payload.get("provenance_summary") or {}).get("confidence_level"),
            "recommended_actions": [
                action.get("code")
                for action in payload.get("recommended_actions") or []
                if isinstance(action, dict)
            ],
        }
    )


def main() -> None:
    client = CareerCopilotApiClient(api_base_url=API_BASE_URL)
    auth = client.login(DEMO_EMAIL, DEMO_PASSWORD)
    token = auth.get("access_token")
    _assert(bool(token), "Demo login did not return an access token")

    applications = client.get_json("/applications", token=token)
    _assert(isinstance(applications, list) and applications, "No applications found")
    seeded_application = next(
        (
            item
            for item in applications
            if isinstance(item, dict)
            and item.get("vacancy_id")
            and item.get("resume_document_id")
            and item.get("cover_letter_document_id")
        ),
        applications[0],
    )
    vacancy_id = str(seeded_application.get("vacancy_id") or "").strip()
    _assert(bool(vacancy_id), "Seeded application vacancy_id is missing")

    resume = client.get_active_document(document_kind="resume", vacancy_id=vacancy_id, token=token)
    cover_letter = client.get_active_document(
        document_kind="cover_letter",
        vacancy_id=vacancy_id,
        token=token,
    )
    interview_sessions = client.list_interview_prep_sessions(token=token)

    _assert(isinstance(interview_sessions, list) and interview_sessions, "No interview prep sessions found")
    interview_session = next(
        (item for item in interview_sessions if isinstance(item, dict) and item.get("id")),
        interview_sessions[0],
    )

    resume_summary = client.get_review_summary(
        entity_type="document",
        entity_id=str(resume["id"]),
        token=token,
    )
    cover_letter_summary = client.get_review_summary(
        entity_type="document",
        entity_id=str(cover_letter["id"]),
        token=token,
    )
    interview_summary = client.get_review_summary(
        entity_type="interview_prep",
        entity_id=str(interview_session["id"]),
        token=token,
    )

    _print_summary("READY RESUME", resume_summary)
    _print_summary("TRUST-RISK COVER LETTER", cover_letter_summary)
    _print_summary("INTERVIEW PREP", interview_summary)

    resume_provenance = resume_summary.get("provenance_summary") or {}
    cover_letter_provenance = cover_letter_summary.get("provenance_summary") or {}
    interview_provenance = interview_summary.get("provenance_summary") or {}

    _assert(resume_summary.get("ready") is True, "Resume should be ready")
    _assert(not (resume_summary.get("blockers") or []), "Resume should not have blockers")
    _assert(resume_provenance.get("confidence_level") == "high", "Resume confidence should be high")

    _assert(
        bool(cover_letter_summary.get("claims_requiring_confirmation")),
        "Cover letter should have claims requiring confirmation",
    )
    _assert(
        cover_letter_provenance.get("confidence_level") in {"low", "needs_review"},
        "Cover letter confidence should be low or needs_review",
    )
    _assert(
        cover_letter_summary.get("ready") is False,
        "Cover letter should remain a trust-risk draft",
    )

    _assert(
        bool(interview_summary.get("gap_risk_items")),
        "Interview prep should have gap-risk items",
    )
    _assert(
        interview_provenance.get("confidence_level") in {"low", "needs_review"},
        "Interview prep confidence should be low or needs_review",
    )

    print()
    print("Demo trust states check passed")


if __name__ == "__main__":
    main()
