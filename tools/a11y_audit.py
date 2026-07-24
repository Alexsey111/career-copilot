"""A11y-аудит веб-фронта через axe-core + Playwright.

Прогоняет 10 страниц авторизованного UI с моком API и собирает
violations. Сохраняет JSON-отчёт в tools/shots/a11y-report.json
и выводит краткую сводку.

Запуск: предварительно поднять `python run_uvicorn_win.py` и
`cd frontend/web && npm run dev` (нужны localhost:7000 и :3000).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

OUT = Path("tools/shots")
OUT.mkdir(exist_ok=True)

# Что мокаем: /auth/me, /consent/, /profile/resume-state, /profile/resumes,
# /me/billing/subscription, /evidence/bank, /vacancies (search + active),
# /applications, /interview/sessions, /interview-prep, /career/strategic,
# /trust/score, /profile/intake/github-public, /documents.
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
MOCK_RESUMES = {"items": [], "total": 0, "active_source_file_id": None}
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
MOCK_VACANCIES = {
    "items": [
        {
            "id": "v-1",
            "title": "Senior Python Developer",
            "company": "Acme",
            "salary_from": 300000,
            "salary_to": 450000,
            "currency": "RUB",
            "url": "https://hh.ru/vacancy/1",
            "source": "hh",
            "published_at": "2026-07-20T10:00:00Z",
            "match_score": 85,
        },
    ],
    "total": 1,
}
MOCK_APPLICATIONS = []
MOCK_EVIDENCE = {
    "achievements": [],
    "project_evidence": [],
    "competency_signals": [],
    "total_evidence": 0,
}
MOCK_STRATEGY = {
    "track_id": "t-1",
    "gaps": [],
    "learning_plan": [],
    "search_tactics": [],
    "provenance": {"method": "deterministic", "version": "v1"},
}
MOCK_TRUST = {
    "score": 75,
    "breakdown": {"evidence_strength": 80, "confirmation_rate": 70, "recency": 75},
    "warnings": [],
}


def mock_payload(url: str) -> dict | None:
    if "/auth/me" in url or url.endswith("/me"):
        return MOCK_ME
    if "/profile/resume-state" in url:
        return MOCK_RESUME_STATE
    if "/profile/resumes" in url and "reuse" not in url:
        return MOCK_RESUMES
    if "/consent/" in url:
        return MOCK_CONSENTS
    if "/me/billing/subscription" in url:
        return MOCK_SUBSCRIPTION
    if "/vacancies" in url and "search" in url:
        return MOCK_VACANCIES
    if "/applications" in url:
        # /applications (массив), /applications/analytics/* (объект),
        # /applications/reminders (массив), /applications/{id}* (объект)
        if "reminders" in url:
            return []
        if "analytics" in url or re.search(r"/applications/[^/\s?]+$", url.split("?")[0]):
            # /applications/{id}, /applications/{id}/status, ...
            return {}
        return MOCK_APPLICATIONS
    if "/evidence" in url:
        # /evidence/bank, /evidence/snippets, /evidence/insights, /evidence/usages
        if "bank" in url:
            return MOCK_EVIDENCE
        # snippets/insights/usages — массивы (snippets/usages) или объект (insights)
        if "insights" in url:
            return {"weak_evidence_count": 0, "missing_metrics_count": 0, "total_snippets": 0}
        return []
    if "/career/strategy" in url or "/career/insights" in url:
        return MOCK_STRATEGY
    if "/trust/score" in url:
        return MOCK_TRUST
    if "/interview" in url:
        # /interview-prep/sessions — массив; /interview-prep/{id}/* — объекты
        if "sessions" in url and "review" not in url and "readiness" not in url:
            return []
        return {}
    if "/documents" in url:
        return {"items": []}
    return {}


PAGES = [
    ("login", "/login", None),
    ("register", "/register", None),
    ("profile", "/profile", "auth"),
    ("vacancies", "/vacancies", "auth"),
    ("applications", "/applications", "auth"),
    ("documents", "/documents", "auth"),
    ("career", "/career", "auth"),
    ("interview", "/interview", "auth"),
    ("evidence", "/evidence", "auth"),
    ("trust", "/trust", "auth"),
    ("billing", "/billing", "auth"),
    ("consent", "/consent", "auth"),
]


def main() -> int:
    axe = Axe()
    report: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        for label, path, kind in PAGES:
            entry: dict = {"page": label, "path": path, "violations": []}
            # Каждая страница в СВОЁМ контексте: имитация prod-навигации
            # (без RSC pre-fetch по Link'ам из предыдущей страницы,
            # который в Next 16 + Turbopack dev ломает cold-страницы).
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            # addInitScript срабатывает ДО любого client-side JS — auth_token
            # будет в localStorage с самого первого document, без промежуточного
            # goto("/login") + setItem, который оставлял React в loading.
            if kind == "auth":
                ctx.add_init_script("() => { try { localStorage.setItem('auth_token', 'demo-token'); } catch (e) {} }")
            page = ctx.new_page()

            def handler(route, request):
                payload = mock_payload(request.url) or {}
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(payload),
                )

            page.route("http://localhost:7000/**", handler)

            try:
                page.goto(f"http://localhost:3000{path}", wait_until="networkidle", timeout=30000)
                # Turbopack dev: networkidle срабатывает до полного mount
                # client-side chunks для cold-страниц.
                if path not in ("/login", "/register"):
                    try:
                        page.wait_for_selector("h1", timeout=15000)
                    except Exception:
                        entry["error"] = f"h1 not found within 15s (path={path})"
                page.wait_for_timeout(500)
                results = axe.run(page)
                entry["violations"] = [
                    {
                        "id": v["id"],
                        "impact": v["impact"],
                        "description": v["description"],
                        "help": v["help"],
                        "nodes_count": len(v["nodes"]),
                        "nodes_html": [n.get("html", "")[:300] for n in v["nodes"][:3]],
                    }
                    for v in results.response.get("violations", [])
                ]
            except Exception as e:
                entry["error"] = str(e)
            report.append(entry)
            ctx.close()

        browser.close()

    # Сводка
    total_critical = sum(
        1 for e in report
        for v in e.get("violations", [])
        if v.get("impact") == "critical"
    )
    total_serious = sum(
        1 for e in report
        for v in e.get("violations", [])
        if v.get("impact") == "serious"
    )

    print(f"Pages audited: {len(report)}")
    print(f"Critical: {total_critical}, Serious: {total_serious}")
    for entry in report:
        vs = entry.get("violations", [])
        crits = [v for v in vs if v.get("impact") == "critical"]
        sers = [v for v in vs if v.get("impact") == "serious"]
        if vs:
            print(
                f"  {entry['page']:14s} critical={len(crits)} serious={len(sers)} "
                f"total={len(vs)} ids={[v['id'] for v in vs]}"
            )
        elif "error" in entry:
            print(f"  {entry['page']:14s} ERROR: {entry['error']}")
        else:
            print(f"  {entry['page']:14s} OK")

    out_path = OUT / "a11y-report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport: {out_path}")

    return 0 if total_critical == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
