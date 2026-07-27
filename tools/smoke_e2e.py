"""End-to-end smoke: #1 GitHub public import + #2 vacancy import-by-URL + analyze.

Запуск с хоста против поднятого docker-compose (API на http://localhost:7000).
Временный диагностический скрипт — не часть тестового набора.
"""
from __future__ import annotations

import json
import sys
import time

import httpx

BASE = "http://localhost:7000/api/v1"
EMAIL = "smoke-e2e@gmail.com"
PASSWORD = "Smoke12345!"

# Реальные внешние URL — суть проверки в том, что контейнер достучится до сети.
HH_URL = "https://hh.ru/vacancy/118221443"  # любая публичная вакансия hh.ru
GITHUB_URL = "https://github.com/sindresorhus"  # публичный профиль с репозиториями


def show(label: str, resp: httpx.Response) -> dict | None:
    print(f"\n=== {label} ===")
    print(f"  {resp.request.method} {resp.request.url} -> {resp.status_code}")
    try:
        body = resp.json()
    except Exception:
        print(f"  body(non-json): {resp.text[:400]!r}")
        return None
    text = json.dumps(body, ensure_ascii=False)
    print(f"  body: {text[:1200]}{'…' if len(text) > 1200 else ''}")
    return body if isinstance(body, dict) else None


def main() -> int:
    rc = 0
    with httpx.Client(timeout=60.0) as c:
        # 1. Register (раздаёт токен сразу).
        r = c.post(f"{BASE}/auth/register", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code == 409:
            r = c.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        body = show("register/login", r)
        if r.status_code not in (200, 201) or not body:
            print("FAIL: не удалось получить токен")
            return 1
        token = body.get("access_token")
        if not token:
            print("FAIL: нет access_token в ответе")
            return 1
        h = {"Authorization": f"Bearer {token}"}

        # 2. Consent (нужен для github-public и AI-фич).
        for ct in ("data_processing", "ai_generation"):
            rc2 = c.post(f"{BASE}/consent/", json={"consent_type": ct}, headers=h)
            show(f"consent {ct}", rc2)

        # 3. #2 — импорт вакансии по URL (сеть: api-контейнер → hh.ru).
        r = c.post(f"{BASE}/vacancies/import-from-url", json={"source_url": HH_URL}, headers=h)
        vac = show("#2 import-from-url", r)
        vacancy_id = vac.get("id") or vac.get("vacancy_id") if vac else None

        if r.status_code in (200, 201) and vacancy_id:
            # 4. analyze (квота vacancy_import + детерминированный анализ).
            r2 = c.post(f"{BASE}/vacancies/{vacancy_id}/analyze", headers=h)
            an = show("#2 analyze", r2)
            if r2.status_code not in (200, 201):
                rc = 1
            elif an and an.get("match_score") in (None, 0):
                print("  WARN: match_score пустой/0 — возможно короткое описание (Bug#73 warning)")
        else:
            rc = 1
            print("  FAIL: импорт по URL не прошёл — #2 не работает в контейнере")

        # 5. #1 — импорт публичного GitHub-профиля (сеть: api-контейнер → github.com).
        r = c.post(
            f"{BASE}/profile/intake/github-public",
            json={
                "profile_url": GITHUB_URL,
                "target_role": "Frontend developer",
                "max_repositories": 3,
                "include_readme": False,
            },
            headers=h,
        )
        gh = show("#1 github-public import", r)
        if r.status_code not in (200, 201):
            rc = 1
            print("  FAIL: github-public не прошёл — #1 не работает в контейнере")
        elif gh:
            print(
                f"  OK: profile_id={gh.get('profile_id')} "
                f"experience={gh.get('experience_count')} projects={gh.get('project_count')} "
                f"achievements={gh.get('achievement_count')} techs={len(gh.get('technologies', []))}"
            )

    print(f"\nSMOKE RESULT rc={rc} ({'PASS' if rc == 0 else 'FAIL'})")
    return rc


if __name__ == "__main__":
    sys.exit(main())