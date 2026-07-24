"""Скриншот /profile с активной секцией «Ранее загруженные файлы».

Моки:
- /auth/me → user
- /profile/resume-state → structured
- /profile/resumes → 2 файла (1 active + 1 superseded) с text_preview
- /consent/list → уже выданные
- /me/billing/subscription → free с usage
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
import json

OUT = Path("tools/shots")
OUT.mkdir(exist_ok=True)

NOW = "2026-07-24T10:00:00Z"
MOCK_ME = {"id": "00000000-0000-0000-0000-000000000001", "email": "demo@local.test"}
MOCK_RESUME_STATE = {
    "resume_import": {"status": "structured", "extraction_id": "demo-ext"},
    "structured_profile": {
        "full_name": "Demo Candidate",
        "headline": "Senior Python Developer",
        "location": "Remote",
        "technologies": ["Python", "FastAPI"],
        "ai_tools": ["OpenAI"],
        "automation_tools": [],
        "extraction_id": "demo-ext",
        "structured_evidence": [],
        "warnings": [],
    },
    "achievements": {"achievements": []},
}
MOCK_RESUMES = {
    "items": [
        {
            "id": "00000000-0000-0000-0000-0000000000aa",
            "original_name": "Alexey_Resume_v3.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 184320,
            "lifecycle_status": "active",
            "lineage_group_id": "00000000-0000-0000-0000-0000000000aa",
            "superseded_by_id": None,
            "created_at": "2026-07-22T09:00:00Z",
            "updated_at": "2026-07-24T08:30:00Z",
            "latest_extraction_id": "demo-ext",
            "latest_extraction_status": "completed",
            "text_preview": "Senior Python Developer with 7 years building FastAPI microservices. Last role: Career Copilot (LangChain, OpenAI, Docker, Postgres)…",
            "detected_format": "pdf",
            "extracted_at": "2026-07-22T09:01:12Z",
            "is_active": True,
            "is_reusable": False,
        },
        {
            "id": "00000000-0000-0000-0000-0000000000bb",
            "original_name": "Resume_old.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "size_bytes": 95600,
            "lifecycle_status": "superseded",
            "lineage_group_id": "00000000-0000-0000-0000-0000000000aa",
            "superseded_by_id": "00000000-0000-0000-0000-0000000000aa",
            "created_at": "2026-05-10T14:22:00Z",
            "updated_at": "2026-07-22T09:00:00Z",
            "latest_extraction_id": "demo-ext-old",
            "latest_extraction_status": "completed",
            "text_preview": "Python developer with 4 years experience. Built internal tools, REST APIs, worked with Django, Flask, PostgreSQL…",
            "detected_format": "docx",
            "extracted_at": "2026-05-10T14:23:01Z",
            "is_active": False,
            "is_reusable": True,
        },
    ],
    "total": 2,
    "active_source_file_id": "00000000-0000-0000-0000-0000000000aa",
}
MOCK_CONSENTS = [
    {"consent_type": "data_processing", "granted": True, "revoked_at": None},
    {"consent_type": "ai_generation", "granted": True, "revoked_at": None},
    {"consent_type": "profile_storage", "granted": True, "revoked_at": None},
]
MOCK_SUBSCRIPTION = {
    "user_id": MOCK_ME["id"],
    "plan": "free",
    "status": "active",
    "stripe_customer_id": None,
    "stripe_subscription_id": None,
    "current_period_end": None,
    "canceled_at": None,
    "usage": [
        {"action": "vacancy_import", "used": 1, "limit": 3, "window_seconds": 3600, "oldest_in_window": "2026-07-24T09:30:00Z"},
        {"action": "ai_request", "used": 2, "limit": 20, "window_days": 30, "oldest_in_window": "2026-07-22T08:00:00Z"},
        {"action": "doc_upload", "used": 1, "limit": 5, "window_days": 30, "oldest_in_window": "2026-07-22T09:00:00Z"},
        {"action": "generated_output", "used": 1, "limit": 5, "window_days": 30, "oldest_in_window": "2026-07-23T14:00:00Z"},
    ],
}


def mock_route(route, payload):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()

    # Моки для всех нужных эндпоинтов
    def handler(route, request):
        url = request.url
        if "/auth/me" in url or url.endswith("/me"):
            return mock_route(route, MOCK_ME)
        if "/profile/resume-state" in url:
            return mock_route(route, MOCK_RESUME_STATE)
        if "/profile/resumes" in url and not "/reuse" in url:
            return mock_route(route, MOCK_RESUMES)
        if "/consent/" in url:
            return mock_route(route, MOCK_CONSENTS)
        if "/me/billing/subscription" in url:
            return mock_route(route, MOCK_SUBSCRIPTION)
        # Всё остальное — пустой 200
        return mock_route(route, {})

    page.route("http://localhost:7000/**", handler)

    # Сначала ставим auth_token в localStorage, чтобы пройти гард (auth)/layout
    page.goto("http://localhost:3000/login")
    page.evaluate("() => localStorage.setItem('auth_token', 'demo-token')")
    page.goto("http://localhost:3000/profile")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)

    out_path = OUT / "resume-history.png"
    page.screenshot(path=str(out_path), full_page=True)

    # Скриншот только секции «Ранее загруженные файлы»
    section = page.locator("text=Ранее загруженные файлы").first
    if section.count() > 0:
        section_path = OUT / "resume-history-section.png"
        section.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.screenshot(path=str(section_path), full_page=True)

    print(f"Screenshot: {out_path}")
    browser.close()
