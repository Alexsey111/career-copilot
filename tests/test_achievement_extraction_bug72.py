"""Регрессионные тесты Bug#72: резюме не парсится, GitHub не дал достижений.

Контекст: пользователь загрузил резюме в markdown-формате, AchievementExtractionService
извлекал 6 «достижений», но они все были мусорные (marketing-описания продуктов,
feature lists, секции «Роль»/«Функционал», пункты «ДОПОЛНИТЕЛЬНО»).

Root cause (двухслойный):
1. ``_split_contribution_blocks`` ловил только ``-`` и ``•`` буллеты — markdown ``*``
   буллеты игнорировались целиком.
2. ``_looks_like_capability_only_contribution`` не ловил AI-product marketing
   фразы типа «AI-платформа для анализа вакансий и подготовки кандидатов» —
   они проходили как achievements (т.к. содержали слабый «подготов»).

После фикса:
- ``*`` буллеты парсятся как blocks.
- Marketing-фразы про AI-продукты/платформы/боты/системы отсекаются capability-фильтром.
- Легитимный кейс «Создал AI-платформу» НЕ ломается (защищён strong_result_marker).
"""

from __future__ import annotations

from app.services.achievement_extraction_service import AchievementExtractionService


def test_markdown_asterisk_bullets_are_parsed() -> None:
    """Bug#72 fix #1: ``*`` буллеты должны парситься как blocks (markdown, RST)."""
    service = AchievementExtractionService()

    signals = service._extract_normalized_contribution_signals(
        """
ПРОЕКТЫ
* Reduced patient discharge delays by 30% coordinating doctors and nurses
* Improved warehouse shift handover process
"""
    )

    titles = [s.title for s in signals]
    assert any("Reduced patient discharge" in t for t in titles), (
        f"* bullet with strong result should be parsed, got {titles!r}"
    )
    assert any("warehouse shift handover" in t for t in titles), (
        f"* bullet without strong result should still be parsed (improved), got {titles!r}"
    )


def test_ai_platform_marketing_phrase_filtered_as_capability() -> None:
    """Bug#72 fix #2: «AI-платформа для X и подготовки Y» — это описание продукта,
    не достижение. Должно отсекаться capability-фильтром."""
    service = AchievementExtractionService()

    signals = service._extract_normalized_contribution_signals(
        """
ПРОЕКТЫ
* AI-платформа для анализа вакансий и подготовки кандидатов
* Built a Telegram bot for legal consultations
"""
    )

    titles = [s.title for s in signals]
    # marketing-фраза отсечена
    assert not any("AI-платформа для анализа" in t for t in titles), (
        f"AI-платформа без action-глагола должна отсекаться, got {titles!r}"
    )
    # легитимный кейс с «Built» — должен остаться
    assert any("Telegram bot" in t for t in titles), (
        f"legit achievement with 'Built' should pass, got {titles!r}"
    )


def test_legit_created_ai_platform_not_filtered() -> None:
    """Защита от over-filtering: «Создал AI-платформу» — легитимное достижение,
    strong_result_marker «создал» должен вывести его из-под capability-фильтра."""
    service = AchievementExtractionService()

    signals = service._extract_normalized_contribution_signals(
        """
ПРОЕКТЫ
* Создал AI-платформу для анализа вакансий с метриками
* Reduced customer churn by 25%
"""
    )

    titles = [s.title for s in signals]
    assert any("Создал AI-платформу" in t for t in titles), (
        f"'Создал AI-платформу' is a legit achievement, got {titles!r}"
    )
    assert any("Reduced customer churn" in t for t in titles)


def test_user_resume_markdown_v2_regression() -> None:
    """Регрессия на полном тексте пользовательского резюме (.diag_resume.txt).

    Ожидаемое поведение: marketing-фразы про AI-продукты, feature lists,
    секции «Роль:»/«Функционал:», пункты «ДОПОЛНИТЕЛЬНО» — НЕ должны
    проходить как achievements. Должны остаться только валидные глаголы
    результата (если они есть в тексте).
    """
    service = AchievementExtractionService()

    user_resume = """
## 🎯 ЦЕЛЬ AI Product Developer

## 🚀 ПРОЕКТЫ

### 🤖 AI Career Copilot (SaaS платформа)

AI-платформа для анализа вакансий и подготовки кандидатов.

**Функционал:**
* анализ вакансий HH
* построение профиля кандидата и банка достижений
* генерация ATS-совместимых резюме и cover letter через LLM

**Роль:** Проектирование архитектуры, реализация MVP, интеграция LLM, продуктовая логика

### ⚖️ Legal Consultation Bot (RAG система)

AI-бот для юридических консультаций на базе законодательства РФ.

**Роль:** Разработка backend, построение RAG-архитектуры, интеграция LLM

## 📚 ДОПОЛНИТЕЛЬНОЕ ОБУЧЕНИЕ
* Data Science и нейросети (2022)
* Python разработка с ChatGPT (2023)
"""

    signals = service._extract_normalized_contribution_signals(user_resume)
    titles = [s.title for s in signals]

    # Marketing-описания продуктов — отсечены
    for forbidden in [
        "AI-платформа для анализа вакансий",
        "AI-бот для юридических",
        "анализ вакансий HH",
        "генерация ATS-совместимых",
        "построение профиля кандидата",
        "Data Science и нейросети",
        "Python разработка с ChatGPT",
        "Проектирование архитектуры",
        "Разработка backend",
    ]:
        assert not any(forbidden in t for t in titles), (
            f"'{forbidden}' should be filtered as capability, got {titles!r}"
        )

    # В этом резюме нет ни одного реального достижения с strong_result_marker,
    # поэтому список должен быть пустым (или содержать только то, что прошло
    # оба фильтра).
    # Главное — НЕ должно быть мусорных маркетинговых заголовков.
    assert len(titles) == 0, (
        f"user resume has no real achievements, but parser returned {titles!r}"
    )
