"""Скриншоты с автологином через localStorage (без бэкенда)."""
import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/tmp/shots")
OUT.mkdir(exist_ok=True)


def shot(page, name, url, before_nav=None):
    if before_nav:
        before_nav(page)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"{name}: navigation error {e}")
        return
    page.wait_for_timeout(2000)
    p = OUT / f"{name}.png"
    page.screenshot(path=str(p), full_page=True)
    body = ""
    try:
        body = page.inner_text("body", timeout=2000)[:600]
    except Exception:
        pass
    print(f"{name} -> {p} ({p.stat().st_size} bytes)")
    print(f"  body: {body!r}")


def main():
    wanted = sys.argv[1].split(",") if len(sys.argv) > 1 else ["all"]

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 800})

        def add_token(page):
            # localStorage auth_token — пустышка, getMe упадёт, но страницы (auth)layout не зависят от бэка.
            page.add_init_script("""
                try {
                    localStorage.setItem('auth_token', 'fake-token-for-screenshot');
                    localStorage.setItem('refresh_token', 'fake-refresh');
                } catch (e) {}
            """)

        if "login" in wanted or "all" in wanted:
            page = ctx.new_page()
            shot(page, "login", "http://localhost:3000/login")
            page.close()

        # Все (auth)/* — обернуты в layout с auth-protected редиректом. Пробуюем на /profile
        # сразу: токен есть, getMe провалится, но увидим хотя бы основной layout (Sidebar + header).
        if "profile" in wanted or "vacancies" in wanted or "billing" in wanted or "trust" in wanted or "career" in wanted:
            page = ctx.new_page()
            add_token(page)
            shot(page, "profile", "http://localhost:3000/profile")
            shot(page, "vacancies", "http://localhost:3000/vacancies")
            shot(page, "billing", "http://localhost:3000/billing")
            shot(page, "trust", "http://localhost:3000/trust")
            shot(page, "career", "http://localhost:3000/career")
            page.close()

        b.close()


if __name__ == "__main__":
    main()
