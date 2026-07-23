"""Снять /interview/<id> с замоканным ответом сессии, где suggested_answer —
объект (как отдаёт бэк после attach_suggested_answers). Это регресс Bug#13."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("tools/shots")
OUT.mkdir(exist_ok=True)

MOCK_ME = {"id": "00000000-0000-0000-0000-000000000001", "email": "demo@local.test"}
MOCK_SESSION = {
    "id": "demo-session",
    "application_id": None,
    "prep_status": "ready",
    "readiness_score": 78,
    "questions": [
        {
            "id": "q-1",
            "prompt": "Расскажите про ваш самый сложный проект с ИИ.",
            "category": "behavioral",
            "competency_name": "Системное мышление",
            "requires_careful_answer": True,
            "recommended_evidence_ids": [],
            # !!! Это объект, не строка — Bug#13
            "suggested_answer": {
                "format": "STAR_plus_tradeoffs",
                "situation": "Пансионат для пожилых, ручной мониторинг 12 палат.",
                "task": "Снизить время реагирования на инциденты.",
                "action": "Развернул модель компьютерного зрения на Raspberry Pi.",
                "result": "Время реакции сократилось с 25 до 4 минут.",
                "tech_stack": ["Python", "PyTorch", "OpenCV", "Raspberry Pi"],
                "tradeoffs": ["Edge vs cloud: выбрал edge ради приватности"],
                "talking_points": ["Senior-уровень", "Production"],
                "source_evidence_id": None,
                "source_title": None,
                "fact_status": "needs_review",
                "grounding_status": "grounded",
                "requires_human_review": True,
                "draft_text": "Ситуация: ...\nЗадача: ...\nДействие: ...\nРезультат: ...",
                "quality": {"score": 0.78, "issues": []},
            },
        }
    ],
    "weak_areas": [],
    "competency_map": {},
    "evidence_links": [],
    "readiness": {
        "readiness_score": 78,
        "prep_status": "ready",
        "blockers": [],
        "warnings": [],
    },
    "created_at": "2026-07-23T00:00:00Z",
}


def install_mocks(context):
    def handler(route, request):
        url = request.url
        if url.endswith("/api/v1/auth/me"):
            return route.fulfill(json=MOCK_ME, status=200)
        if "/api/v1/interview-prep/sessions/" in url and url.endswith("/readiness"):
            return route.fulfill(json=MOCK_SESSION["readiness"], status=200)
        if "/api/v1/interview-prep/sessions/" in url:
            return route.fulfill(json=MOCK_SESSION, status=200)
        return route.continue_()
    context.route("**/api/v1/**", handler)


def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else "demo-session"
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1024, "height": 900})
        install_mocks(ctx)
        ctx.add_init_script("""
            try {
                localStorage.setItem('auth_token', 'fake-token-mock');
                localStorage.setItem('refresh_token', 'fake-refresh');
            } catch (e) {}
        """)
        page = ctx.new_page()
        try:
            page.goto("http://localhost:3000/", wait_until="domcontentloaded", timeout=10000)
        except Exception:
            pass
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            page.goto(
                f"http://localhost:3000/interview/{session_id}",
                wait_until="domcontentloaded",
                timeout=20000,
            )
        except Exception as e:
            print(f"nav error {e}")
        try:
            page.wait_for_timeout(2500)
        except Exception:
            pass
        out = OUT / f"interview-{session_id}-bug13.png"
        page.screenshot(path=str(out), full_page=True)
        try:
            body = page.inner_text("body", timeout=2000)[:500]
            body_safe = body.encode("ascii", "ignore").decode("ascii")
        except Exception:
            body_safe = ""
        print(f"-> {out} ({out.stat().st_size} bytes)")
        print(f"  body: {body_safe!r}")
        if errors:
            print(f"  PAGEERRORS: {errors}")
        else:
            print("  pageerrors: none")
        b.close()


if __name__ == "__main__":
    main()
