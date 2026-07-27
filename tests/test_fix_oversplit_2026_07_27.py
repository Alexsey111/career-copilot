"""Регрессия ноута #3 (2026-07-27): over-split must_have склеивал формы слов
через «;» в fit-карте («автоматизацией; автоматизации; автоматизаций;
автоматизировать; агентов»).

Корень: ``VacancyAnalysisService._group_requirements`` при >5 пунктов звал
``_merge_requirements``, который брал top-5 keywords группы через «;» —
получались мусорные склейки лемм + неродственных слов. match_score считался
ДО группировки, UI показывает slice(0,5) — группировка была не нужна и
портила читаемость. Методы удалены.

Тест: на >5 пунктов требований с повтором корня «автоматиз» must_have —
список реальных фраз, без «;»-склеек лемм. Детерминированный, БЕЗ LLM.
"""
from app.services.vacancy_analysis_service import (
    NICE_TO_HAVE_START_HEADINGS,
    REQUIREMENT_START_HEADINGS,
    STOP_HEADINGS,
    VacancyAnalysisService,
)

# Реальная hh-вакансия «Технический ассистент по AI и автоматизации»
# (эмодзи уже вырезаны нормализацией импорта, fix #3): раздел «Что нужно будет
# делать» с >5 пунктами, несколько содержат корень «автоматиз».
VACANCY_TEXT = """Технический ассистент по AI и автоматизации

Что нужно будет делать:
- Автоматизация рутинных процессов с помощью AI-инструментов
- Помощь руководителю в технических задачах
- Настройка ПО и доступов для сотрудников
- Взаимодействие с командой по автоматизации
- Автоматизация тестирования и контроля качества
- Подключение AI-агентов и нейросетей
- Работа с Google Документами и сервисами

Ключевые навыки:
Настройка ПО, Аналитическое мышление
"""


def test_group_requirements_removed() -> None:
    """Dead-методы _group_requirements/_merge_requirements/_categorize_
    requirement удалены — больше не склеивают пункты через «;»."""
    service = VacancyAnalysisService()
    for name in ("_group_requirements", "_merge_requirements", "_categorize_requirement"):
        assert not hasattr(service, name), f"{name} should be removed"


def test_must_have_has_no_semicolon_lemma_merging() -> None:
    """Главный сценарий #87: >5 пунктов требований с корнем «автоматиз» —
    must_have остаётся списком реальных фраз, без «;»-склеек лемм
    (раньше было «автоматизацией; автоматизации; автоматизаций; …»)."""
    service = VacancyAnalysisService()
    lines = service._clean_lines(VACANCY_TEXT)
    must_have = service._extract_section_items(
        lines,
        start_headings=REQUIREMENT_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )

    assert len(must_have) >= 5, f"expected >=5 requirements, got {must_have}"
    # Ни один пункт — не «;»-склейка лемм (form-merging больше не происходит).
    for item in must_have:
        # Реальная фраза может содержать «;» только если он был в источнике
        # (здесь нет) — поэтому «; » = признак _merge_requirements.
        assert "; " not in item, f"semicolon-merge leaked into must_have: {item!r}"

    # Реальные фразы про автоматизацию различимы (не схлопнуты в одну «;»).
    joined = " ".join(must_have).lower()
    assert "автоматиз" in joined


def test_must_have_preserves_real_phrases_not_keywords() -> None:
    """Требования — осмысленные фразы («Автоматизация рутинных процессов…»),
    не обрубленные top-5 keywords из _merge_requirements."""
    service = VacancyAnalysisService()
    lines = service._clean_lines(VACANCY_TEXT)
    must_have = service._extract_section_items(
        lines,
        start_headings=REQUIREMENT_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )

    # Хотя бы одна фраза — многословная (>=3 слов), не одиночный keyword.
    multiword = [m for m in must_have if len(m.split()) >= 3]
    assert multiword, f"expected multiword phrases, got {must_have}"
    # Конкретная фраза про «рутинные процессы» сохранена, не обрублена.
    assert any("рутинн" in m.lower() or "процесс" in m.lower() for m in must_have)


def test_nice_to_have_also_unmerged() -> None:
    """nice_to_have тоже не группируется (вызов _group_requirements удалён
    для обоих)."""
    text = """Вакансия

Будет преимуществом:
- Опыт использования Codex
- Знание Google Документов
- CRM-опыт
- Telegram-боты
- Vibe-coding
- Нейроассистенты
- No-code инструменты
"""
    service = VacancyAnalysisService()
    lines = service._clean_lines(text)
    nice = service._extract_section_items(
        lines,
        start_headings=NICE_TO_HAVE_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )
    assert len(nice) >= 5
    for item in nice:
        assert "; " not in item, f"semicolon-merge leaked into nice_to_have: {item!r}"


def test_comma_inside_phrase_does_not_create_stub_fragment() -> None:
    """Запятая внутри фразы-предложения («работа с инструментами,
    связанными с сервисами») не должна давать обрубок «Связанных с сервисами»
    как отдельное требование. После fix склейки обрубков-продолжений
    (FRAGMENT_START_WORDS: причастия/предлоги/союзы) фраза остаётся целой."""
    from app.services.requirement_canonicalizer import split_atomic_requirements

    result = split_atomic_requirements("работа с инструментами, связанными с сервисами")
    assert result == ["работа с инструментами, связанными с сервисами"]

    # Легитимный список технологий через запятую — всё ещё сплитится.
    assert split_atomic_requirements("Python, FastAPI, PostgreSQL") == [
        "Python",
        "FastAPI",
        "PostgreSQL",
    ]