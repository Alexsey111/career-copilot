"""Регрессия #3b (2026-07-27): match_score=0 при реальном пересечении навыков.

Корневая причина (НЕ embeddings): детерминированный матчер
``VacancyAnalysisService._compare_with_profile`` использует каталог скиллов
``app/domain/skills/catalog.py`` через ``extract_keywords`` /
``keyword_present`` / ``get_related_skills``. Каталог не распознавал
AI-термины (ИИ, AI-инструменты, нейросети, чат-боты, Codex, Vibe-coding) →
must_have-фразы без catalog-совпадения падали в exact-phrase-матч и не
матчились. Плюс ``_compute_category_score`` считал элемент matched, сравнивая
canonical-ключ («automation») со словами сырой русской фразы («автоматизацией»)
— инфлексия не совпадала, category_score всегда 0.

Фиксы (детерминированные, БЕЗ LLM/эмбеддингов; общие AI-синонимы, не хардкод
под конкретное резюме — «люди будут и других профессий»):
- Каталог: новые скиллы Artificial Intelligence / Neural Networks / Chat Bots /
  AI Tools / AI Coding + zero-code/зерокодинг в No-code, с cross-related_skills.
- ``_compute_category_score``: matched-детекция по ``requirement_text`` из
  strengths (исходный текст пункта), а не word-split canonical vs inflected.

АРХ-ограничение: LLM = NLG-слой поверх проанализированных документов; анализ
остаётся детерминированным. Каталог/матчер — не LLM.
"""
from types import SimpleNamespace

from app.domain.skills.catalog import SKILL_DEFINITIONS
from app.domain.skills.utils import extract_keywords, get_related_skills, keyword_present
from app.services.vacancy_analysis_service import VacancyAnalysisService


CANONICAL_NAMES = {s.canonical_name for s in SKILL_DEFINITIONS}


def test_catalog_defines_ai_skill_synonyms() -> None:
    # Общие AI-синонимы присутствуют в каталоге (не хардкод под резюме —
    # любая AI-вакансия/профиль получает распознавание).
    for name in (
        "Artificial Intelligence",
        "Neural Networks",
        "Chat Bots",
        "AI Tools",
        "AI Coding",
    ):
        assert name in CANONICAL_NAMES, name


def test_extract_keywords_recognizes_ai_terms_in_vacancy_phrases() -> None:
    # must_have-фразы hh.ru с AI-терминами теперь дают catalog-ключи.
    assert "Artificial Intelligence" in extract_keywords("Разработка новых технических решений с помощью ИИ")
    assert "Artificial Intelligence" in extract_keywords("Автоматизация и AI-инструментами")
    assert "AI Tools" in extract_keywords("Подключение AI-инструментов и ИИ-агентов")
    assert "Chat Bots" in extract_keywords("Проверка корректности работы ботов")
    assert "Chat Bots" in extract_keywords("Опыт работы с Telegram-ботами")
    assert "Neural Networks" in extract_keywords("Оркестраторов AI и других нейросетей")
    assert "AI Coding" in extract_keywords("Опыт использования Codex")
    assert "AI Coding" in extract_keywords("Vibe-coding и нейроассистенты")
    assert "No-code" in extract_keywords("zero-code инструменты")


def test_keyword_present_matches_russian_ai_in_profile() -> None:
    # Профиль на русском («Искусственный интеллект», «ИИ-система») удовлетворяет
    # catalog-ключу Artificial Intelligence через patterns.
    assert keyword_present("Artificial Intelligence", "Искусственный интеллект, LLM, Python")
    assert keyword_present("Artificial Intelligence", "Разработал ИИ-систему мониторинга")
    assert keyword_present("Neural Networks", "Нейросети (промптинг)")
    assert keyword_present("Chat Bots", "Чат-боты для поддержки")


def test_related_skills_link_ai_tools_to_ai() -> None:
    # Вакансия с «AI-инструментами» должна матчиться профилем, где есть ИИ,
    # через related_skills (AI Tools → Artificial Intelligence).
    related = set(get_related_skills("AI Tools"))
    assert "Artificial Intelligence" in related
    # И обратно — профиль с «нейросетями» закрывает вакансию с ИИ.
    assert "Artificial Intelligence" in set(get_related_skills("Neural Networks"))


def _fake_profile(*, headline: str, summary: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        headline=headline,
        summary=summary,
        target_roles_json=[],
        experiences=[],
        achievements=[],
    )


def test_match_score_nonzero_when_ai_skills_overlap() -> None:
    """Главный сценарий #3b: профиль AI-кандидата и AI-вакансия дают
    ненулевой match_score (раньше 0 — каталог не знал AI-терминов)."""
    service = VacancyAnalysisService()
    profile = _fake_profile(
        headline="Prompt Engineering, Data Science",
        summary="Python, Git, Искусственный интеллект, LLM, Нейросети, Чат-боты, API, SQL",
    )
    must_have = [
        "Разработка новых технических решений с помощью ИИ",
        "Автоматизация и AI-инструментами",
        "Проверка корректности работы ботов",
        "Подключение AI-инструментов и ИИ-агентов",
    ]
    nice_to_have = ["Опыт использования Codex", "Оркестраторов AI и других нейросетей"]

    strengths, gaps, score = service._compare_with_profile(
        profile, [], must_have=must_have, nice_to_have=nice_to_have
    )

    assert score is not None and score > 0, f"expected nonzero score, got {score}"
    strength_keywords = {s["keyword"] for s in strengths}
    assert "Artificial Intelligence" in strength_keywords
    assert "Chat Bots" in strength_keywords
    assert "AI Tools" in strength_keywords


def test_match_score_low_when_no_ai_overlap_no_false_positive() -> None:
    """Профиль без AI-навыков не должен получать высокий score по AI-вакансии
    (нет ложного срабатывания после расширения каталога)."""
    service = VacancyAnalysisService()
    profile = _fake_profile(
        headline="Бухгалтер",
        summary="1С, Excel, налоговый учёт, первичная документация",
    )
    must_have = [
        "Разработка новых технических решений с помощью ИИ",
        "Подключение AI-инструментов и ИИ-агентов",
        "Проверка корректности работы ботов",
    ]
    nice_to_have = ["Опыт использования Codex"]

    strengths, gaps, score = service._compare_with_profile(
        profile, [], must_have=must_have, nice_to_have=nice_to_have
    )

    # Ничего из AI не сматчилось — strengths пуст, score 0 (не ложный позитив).
    assert strengths == []
    assert score is None or score == 0
    # Все требования ушли в gaps (canonical-ключи и/или компактные подписи).
    assert len(gaps) >= len(must_have) + len(nice_to_have)


def test_compute_category_score_counts_russian_inflected_match() -> None:
    """Регрессия бага _compute_category_score: matched-детекция по
    requirement_text (а не word-split canonical vs inflected). Раньше
    «автоматизацией» ≠ «automation» → category_score 0 даже при матче."""
    service = VacancyAnalysisService()
    must_have = ["Автоматизация и AI-инструментами", "Помощь с доступами"]
    strengths = [
        {
            "keyword": "Artificial Intelligence",
            "scope": "must_have",
            "requirement_text": "Автоматизация и AI-инструментами",
            "weight": 3,
            "evidence": "profile_keyword_or_alias_overlap",
        }
    ]
    gaps = [
        {
            "keyword": "Помощь с доступами",
            "scope": "must_have",
            "requirement_text": "Помощь с доступами",
            "weight": 3,
            "reason": "not_found_in_profile_text",
        }
    ]

    category_score = service._compute_category_score(strengths, gaps, must_have, [])

    # 1 из 2 пунктов matched → soft_skills 1/2 = 50% (было 0 до фикса).
    assert category_score > 0
    assert category_score == 50