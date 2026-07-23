"""Снять /onboarding/consent в двух состояниях: (1) свежий пользователь
(нет data_processing — required чекнуты) и (2) decline-flow (апology).

Это регресс для #14: /consent теперь в онбординге, обязательные active by default.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("tools/shots")
OUT.mkdir(exist_ok=True)

MOCK_ME = {"id": "00000000-0000-0000-0000-000000000001", "email": "demo@local.test"}

# (1) Свежий пользователь — data_processing ещё не выдавалось
MOCK_CONSENTS_FRESH = [
    {"consent_type": "data_processing", "description": "Согласие на обработку персональных данных", "required": True, "version": "1.0", "granted": False, "granted_at": None, "revoked_at": None},
    {"consent_type": "ai_generation", "description": "Согласие на использование AI для генерации документов", "required": True, "version": "1.0", "granted": False, "granted_at": None, "revoked_at": None},
    {"consent_type": "profile_storage", "description": "Согласие на хранение профиля и данных", "required": True, "version": "1.0", "granted": False, "granted_at": None, "revoked_at": None},
    {"consent_type": "analytics_tracking", "description": "Согласие на сбор аналитики поиска работы", "required": False, "version": "1.0", "granted": False, "granted_at": None, "revoked_at": None},
    {"consent_type": "third_party_sharing", "description": "Согласие на передачу данных третьим лицам", "required": False, "version": "1.0", "granted": False, "granted_at": None, "revoked_at": None},
]


def make_handler(consents):
    def handler(route, request):
        url = request.url
        if "/api/v1/auth/me" in url:
            return route.fulfill(json=MOCK_ME, status=200)
        if "/api/v1/consent" in url:
            return route.fulfill(json=consents, status=200)
        return route.continue_()
    return handler


def shoot(name: str, url: str, consents, click_selector: str | None = None):
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1024, "height": 900})
        ctx.route("**/*", make_handler(consents))
        ctx.add_init_script("""
            try {
                localStorage.setItem('auth_token', 'fake-token-mock');
                localStorage.setItem('refresh_token', 'fake-refresh');
            } catch (e) {}
        """)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            page.goto("http://localhost:3000/", wait_until="domcontentloaded", timeout=10000)
        except Exception:
            pass
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            print(f"{name}: nav error {e}")
        try:
            page.wait_for_timeout(2500)
        except Exception:
            pass
        if click_selector:
            try:
                page.click(click_selector, timeout=5000)
                page.wait_for_timeout(800)
            except Exception as e:
                print(f"  click error: {e}")
        out = OUT / f"{name}.png"
        page.screenshot(path=str(out), full_page=True)
        try:
            body = page.inner_text("body", timeout=2000)[:600]
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


def main():
    # 1) Свежий пользователь на экране онбординга (required active by default)
    shoot(
        "onboarding-consent-fresh",
        "http://localhost:3000/onboarding/consent",
        MOCK_CONSENTS_FRESH,
    )
    # 2) Decline: открыть напрямую и кликнуть «Я не согласен»
    shoot(
        "onboarding-consent-declined",
        "http://localhost:3000/onboarding/consent",
        MOCK_CONSENTS_FRESH,
        click_selector='button:has-text("Я не согласен")',
    )
    # 3) Гард: /profile со свежим user → редирект на /onboarding/consent
    shoot(
        "guard-profile-to-onboarding",
        "http://localhost:3000/profile",
        MOCK_CONSENTS_FRESH,
    )


if __name__ == "__main__":
    main()
