"""Test generation quality using deterministic (no-LLM) mode with real resumes/vacancies from 111/."""

import asyncio
import os
import re
import sys
from pathlib import Path
from uuid import uuid4

# Setup environment
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://career_user:career_pass@localhost:5433/career_copilot_test")
os.environ.setdefault("SYNC_DATABASE_URL", "postgresql+psycopg://career_user:career_pass@localhost:5433/career_copilot_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-12345678")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("AI_DEFAULT_MODEL", "mock-model")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import AsyncSessionLocal
from app.models import User, CandidateProfile, CandidateExperience, CandidateAchievement, Vacancy, VacancyAnalysis
from app.services.resume_generation_service import ResumeGenerationService
from app.services.cover_letter_generation_service import CoverLetterGenerationService
from app.services.vacancy_analysis_service import VacancyAnalysisService
from app.services.profile_structuring_service import ProfileStructuringService
from sqlalchemy import select, text

DATA_DIR = Path(__file__).resolve().parents[1] / "111"

RESUME_VACANCY_PAIRS = [
    ("Backend Developer.txt", "вакансия разработчика.txt"),
    ("Марина Соколова - Бухгалтер.txt", "Бухгалтер вакансия.txt"),
    ("Графический дизайнер.txt", "Графический дизайнер вакансия.txt"),
]


def load_file(name: str) -> str:
    path = DATA_DIR / name
    return path.read_text(encoding="utf-8")


async def setup_test_data(session):
    user = User(
        email=f"test-gen-{uuid4().hex[:8]}@test.com",
        password_hash=None,
        auth_provider="test",
    )
    session.add(user)
    await session.flush()

    resume_text = load_file("Backend Developer.txt")
    profile = CandidateProfile(
        user_id=user.id,
        full_name="Иван Петров",
        headline="Backend Developer",
        location="Москва",
        summary=resume_text,
    )
    session.add(profile)
    await session.flush()

    experience = CandidateExperience(
        profile_id=profile.id,
        company="ООО CloudSoft",
        role="Backend Developer",
        description_raw="Разработка REST API на FastAPI, интеграция PostgreSQL, Docker контейнеризация, настройка CI/CD",
    )
    session.add(experience)
    await session.flush()

    achievements_data = [
        ("Сократил время ответа API на 35%", "Оптимизировал запросы к БД", "Снизил p99 latency с 200мс до 130мс"),
        ("Перевёл монолитный сервис на микросервисную архитектуру", "Разделил на 5 сервисов", "Снизил время деплоя на 60%"),
        ("Настроил автоматическое тестирование", "Pytest + GitHub Actions", "Покрытие выросло с 40% до 85%"),
    ]

    for i, (title, action, result) in enumerate(achievements_data):
        ach = CandidateAchievement(
            profile_id=profile.id,
            experience_id=experience.id,
            title=title,
            action=action,
            result=result,
            fact_status="confirmed",
            order_index=i,
        )
        session.add(ach)

    await session.flush()
    return user, profile


async def run_test(session, user, profile, resume_file, vacancy_file):
    print(f"\n{'='*60}")
    print(f"РЕЗЮМЕ: {resume_file}")
    print(f"ВАКАНСИЯ: {vacancy_file}")
    print(f"{'='*60}")

    vacancy_text = load_file(vacancy_file)

    from app.domain.vacancy_title_extractor import extract_vacancy_title
    title_from_filename = vacancy_file.replace(".txt", "").strip()
    extracted_title = extract_vacancy_title(vacancy_text, fallback=title_from_filename)

    vacancy = Vacancy(
        user_id=user.id,
        source="manual",
        title=extracted_title,
        company="Тестовая компания",
        location="Москва",
        description_raw=vacancy_text,
        normalized_json={},
    )
    session.add(vacancy)
    await session.flush()

    analysis_service = VacancyAnalysisService()
    analysis = await analysis_service.analyze_vacancy(
        session,
        vacancy_id=vacancy.id,
        user_id=user.id,
    )
    await session.flush()

    print(f"\n--- АНАЛИЗ ВАКАНСИИ ---")
    print(f"Match Score: {analysis.match_score}%")
    print(f"Must Have: {len(analysis.must_have_json)} требований")
    for req in analysis.must_have_json[:5]:
        print(f"  - {req.get('text', req)}")
    print(f"Nice to Have: {len(analysis.nice_to_have_json)} требований")
    for req in analysis.nice_to_have_json[:3]:
        print(f"  - {req.get('text', req)}")
    print(f"Strengths: {len(analysis.strengths_json)} совпадений")
    for s in analysis.strengths_json[:3]:
        print(f"  + {s.get('keyword', s)}")
    print(f"Gaps: {len(analysis.gaps_json)} пробелов")
    for g in analysis.gaps_json[:3]:
        print(f"  ! {g.get('keyword', g)}")

    if analysis.language_tone_hints_json:
        hints = analysis.language_tone_hints_json
        print(f"Tone: {hints.get('tone', 'N/A')}, Language: {hints.get('language', 'N/A')}")
        for h in hints.get("style_hints", []):
            print(f"  * {h}")

    resume_service = ResumeGenerationService()
    resume_doc = await resume_service.generate_resume(
        session,
        vacancy_id=vacancy.id,
        user_id=user.id,
    )
    await session.flush()

    print(f"\n--- СГЕНЕРИРОВАННОЕ РЕЗЮМЕ ---")
    print(f"Version: {resume_doc.version_label}")
    content = resume_doc.content_json
    rendered = resume_doc.rendered_text or ""
    if rendered:
        lines = rendered.strip().split("\n")
        print(f"Строк: {len(lines)}")
        for line in lines[:25]:
            print(f"  {line}")
        if len(lines) > 25:
            print(f"  ... ({len(lines) - 25} строк)")

    letter_service = CoverLetterGenerationService()

    for variant in ["standard", "short", "career_switch"]:
        letter_doc = await letter_service.generate_cover_letter(
            session,
            vacancy_id=vacancy.id,
            user_id=user.id,
            variant=variant,
        )
        await session.flush()

        print(f"\n--- СОПРОВОДИТЕЛЬНОЕ ПИСЬМО ({variant}) ---")
        print(f"Version: {letter_doc.version_label}")
        letter_text = letter_doc.rendered_text or ""
        if letter_text:
            lines = letter_text.strip().split("\n")
            print(f"Символов: {len(letter_text)}")
            for line in lines[:15]:
                print(f"  {line}")
            if len(lines) > 15:
                print(f"  ... ({len(lines) - 15} строк)")


async def main():
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))

        user, profile = await setup_test_data(session)
        await session.commit()

        for resume_file, vacancy_file in RESUME_VACANCY_PAIRS:
            try:
                await run_test(session, user, profile, resume_file, vacancy_file)
                await session.commit()
            except Exception as e:
                print(f"\nОшибка: {e}")
                await session.rollback()

    print(f"\n{'='*60}")
    print("ТЕСТ ГЕНЕРАЦИИ ЗАВЕРШЁН")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
