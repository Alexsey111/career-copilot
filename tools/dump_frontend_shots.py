"""Скриншоты ключевых страниц фронта с подменой auth/me и resume-state,
чтобы UI (auth)layout показался без живого бэкенда.

Делает минимальные моки через playwright route, чтобы страницы отрисовали
свою разметку для визуального ревью. Реальные данные не используются.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/tmp/shots")
OUT.mkdir(exist_ok=True)

# Что мокаем: auth/me (любой токен) → user; resume-state → структура; vacancies/search → items.
MOCK_ME = {"id": "00000000-0000-0000-0000-000000000001", "email": "demo@local.test"}
MOCK_RESUME = {
    "resume_import": {"status": "structured", "extraction_id": "demo-ext"},
    "structured_profile": {
        "full_name": "Demo Candidate",
        "headline": "Senior Python Developer",
        "location": "Remote",
        "technologies": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
        "ai_tools": ["OpenAI API", "LangChain"],
        "automation_tools": ["n8n", "Airflow"],
        "extraction_id": "demo-ext",
        "structured_evidence": [
            {"title": "Built internal API gateway", "skills": ["FastAPI", "PostgreSQL"]},
            {"title": "Migrated legacy monolith to microservices", "skills": ["Docker", "Kubernetes"]},
        ],
        "warnings": [],
    },
    "achievements": {
        "achievements": [
            {"id": "ach-1", "title": "Reduced API latency by 40%", "fact_status": "confirmed", "source": "resume"},
            {"id": "ach-2", "title": "Led team of 5 engineers", "fact_status": "needs_confirmation", "source": "resume"},
        ]
    },
}
# Bug#3.2: oldest_in_window заполняется бэком (UTC ISO). Для UI-мока
# вычислим «через 25 мин» и «через 14 дней 6 ч» от текущего момента.
from datetime import datetime, timedelta, timezone

_NOW = datetime.now(timezone.utc)
_VACANCY_OLDEST = (_NOW - timedelta(minutes=35)).isoformat().replace("+00:00", "Z")
_AI_OLDEST = (_NOW - timedelta(days=16)).isoformat().replace("+00:00", "Z")
_UPLOAD_OLDEST = (_NOW - timedelta(days=2, hours=4)).isoformat().replace("+00:00", "Z")
_OUTPUT_OLDEST = (_NOW - timedelta(days=27)).isoformat().replace("+00:00", "Z")

MOCK_SUBSCRIPTION = {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "plan": "free",
    "status": "active",
    "stripe_customer_id": None,
    "stripe_subscription_id": None,
    "current_period_end": None,
    "canceled_at": None,
    "usage": [
        {
            "action": "vacancy_import",
            "used": 3,
            "limit": 3,
            "window_seconds": 3600,
            "oldest_in_window": _VACANCY_OLDEST,
        },
        {
            "action": "ai_request",
            "used": 8,
            "limit": 20,
            "window_days": 30,
            "oldest_in_window": _AI_OLDEST,
        },
        {
            "action": "doc_upload",
            "used": 1,
            "limit": 5,
            "window_days": 30,
            "oldest_in_window": _UPLOAD_OLDEST,
        },
        {
            "action": "generated_output",
            "used": 3,
            "limit": 3,
            "window_days": 30,
            "oldest_in_window": _OUTPUT_OLDEST,
        },
    ],
}
MOCK_VACANCIES = {
    "items": [
        {"id": "v-1", "title": "Senior Python Developer", "company": "Acme", "location": "Remote", "salary_from": 250000, "salary_to": 380000, "similarity": 0.91, "created_at": "2026-07-20T00:00:00Z"},
        {"id": "v-2", "title": "Backend Engineer (FastAPI)", "company": "BetaSoft", "location": "Moscow", "salary_from": 200000, "salary_to": 320000, "similarity": 0.78, "created_at": "2026-07-19T00:00:00Z"},
    ]
}

PAGES = [
    ("profile", "http://localhost:3000/profile", "resume-state"),
    ("vacancies", "http://localhost:3000/vacancies", "vacancies"),
    ("billing", "http://localhost:3000/billing", "subscription"),
    ("trust", "http://localhost:3000/trust", None),
    ("career", "http://localhost:3000/career", None),
]


def install_mocks(context):
    def handler(route, request):
        url = request.url
        if url.endswith("/api/v1/auth/me"):
            return route.fulfill(json=MOCK_ME, status=200)
        if url.endswith("/api/v1/profile/resume-state"):
            return route.fulfill(json=MOCK_RESUME, status=200)
        if "/api/v1/me/billing/subscription" in url:
            return route.fulfill(json=MOCK_SUBSCRIPTION, status=200)
        if "/api/v1/vacancies/search" in url:
            return route.fulfill(json=MOCK_VACANCIES, status=200)
        # Default: pass through (will 404, but page will render with empty state)
        return route.continue_()
    context.route("**/api/v1/**", handler)


def main():
    wanted = sys.argv[1].split(",") if len(sys.argv) > 1 else [n for n, _, _ in PAGES]
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1024, "height": 700})

        # Моки регистрируем ДО add_init_script и навигации, чтобы
        # перехватить первый же fetch /auth/me при mount AuthContext.
        install_mocks(ctx)
        ctx.add_init_script("""
            try {
                localStorage.setItem('auth_token', 'fake-token-mock');
                localStorage.setItem('refresh_token', 'fake-refresh');
            } catch (e) {}
        """)
        page = ctx.new_page()
        # Прогрев — зайдём на /, чтобы AuthContext смонтировался с моком.
        try:
            page.goto("http://localhost:3000/", wait_until="domcontentloaded", timeout=10000)
        except Exception:
            pass
        for name, url, _ in PAGES:
            if name not in wanted:
                continue
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                print(f"{name}: nav error {e}")
                continue
            try:
                page.wait_for_timeout(2000)
            except Exception:
                pass
            p_out = OUT / f"{name}-mock.png"
            page.screenshot(path=str(p_out), full_page=True)
            try:
                body = page.inner_text("body", timeout=2000)[:400]
                # Encode-safety: cp1251 stdout не вывозит эмодзи — отрежем их.
                body_safe = body.encode("ascii", "ignore").decode("ascii")
            except Exception:
                body_safe = ""
            print(f"{name} -> {p_out} ({p_out.stat().st_size} bytes)")
            print(f"  body: {body_safe!r}")
        b.close()


if __name__ == "__main__":
    main()
