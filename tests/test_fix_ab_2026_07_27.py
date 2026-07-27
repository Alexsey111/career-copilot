"""Регрессия трёх жалоб ручного теста 2026-07-27 (после #1/#2/#3/#3b):

- **Fix A** «Подтверждено 2/2 так и не извлек 3»: achievement-экстрактор
  (ОТДЕЛЬНЫЙ путь от structuring #2b) отбрасывал 3-ю стажировку, потому что
  inline trailing section-heading «О себе:» склеивал пункт 3 с prose-разделом
  «О себе», и responsibility-фильтр гасил пункт за маркер «взаимодейств» из
  самоописания. Фикс: ``_split_numbered_blocks`` обрывает блок на trailing
  heading (симметрично structuring #2d), ``_strip_trailing_section_heading`` +
  «О СЕБЕ»/«ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ» в inline-layout-headings.
- **Fix B** «гит хаб как не учитывался»: ``_build_profile_corpus`` не включал
  ``profile.technologies_json`` (куда GitHub-intake пишет языки репозиториев,
  а structuring резюме — весь стек). Профиль, созданный импортом GitHub,
  матчера не видел вовсе. Фикс: technologies_json в corpus.

АРХ-ограничение (verbatim): «LLM у нас участвует только в качественном
написании документов… модель у нас не анализирует ни резюме ни вакансию».
Оба фикса — детерминированные эвристики, БЕЗ LLM/эмбеддингов; общие, БЕЗ
хардкодов под конкретное резюме («люди будут и без стажировок и других
профессий»).
"""
from types import SimpleNamespace

from app.services.achievement_extraction_service import AchievementExtractionService
from app.services.vacancy_analysis_service import VacancyAnalysisService

# Реальный текст резюме Перминова (тот же, что в structuring-тестах #2):
# 3 стажировки в «Дополнительные сведения», пункт 3 заканчивается на
# «» О себе:» — воспроизводит баг Fix A.
PERMINOV_RESUME = """г.Барнаул, Россия, 656060
ул. Антона Петрова, д.262, кв. 306
(+7) 9039115133
lev.21.06.2005@gmail.com
https://github.com/Alexsey111
Перминов Алексей
30.11.1972 г.р.
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, Нейросети (промптинг), Создание нейроассистентов, Чат-боты, API, SQL,
Анализ данных, Tensorflow, Vibe-coding.
Желаемая должность
Prompt Engineering, Data Science, Vibe-coding
ОПЫТ РАБОТЫ
Алтайский Государственный Медицинский Университет, электромонтер по ремонту и обслуживанию электрооборудования
01.01.2015 - по настоящее время
ОБРАЗОВАНИЕ
Алтайский государственный технический университет имени И.И. Ползунова, Барнаул инженер, Автомобиле- и тракторостроение
1999 - 2001
Рязанское высшее воздушно-десантное командное училище им. В.Ф. Маргелова, Рязань инженерный, командная тактическая воздушно-
десантных войск 1993 - 1997
Курсы
Data Science, нейронные сети, машинное обучение и
искусственный интеллект университет искусственного интеллекта 2022 Программист на Python с нуля с помощью ChatGPT
университет зерокодинга 2023 Аналитик данных с нуля с помощью ChatGPT университет зерокодинга
2024
Промпт-инжиниринг университет зерокодинга
2025
Нейросети PRO университет зерокодинга 2026 Дополнительные сведения Прошел 3 стажировки по направлению Data Science:
1. Создание ИИ-системы для мониторинга безопасности в пансионатах для пожилых (ООО «СГЦ ОПЕКА»).
2. Автоматизированный ИИ-контроль качества ПВХ оконных изделий по изображениям и видео
(ООО «ТД «Проплекс»).
3. «ИИ-анализ текстовых отзывов населения о социальных объектах инфраструктуры для прогнозирования развития городской среды и оценки
устойчивого развития территорий (Московский Политехнический Университет)» О себе:
Развиваюсь в области промпт-инжиниринга, создания нейроассистентов и аналитики данных,
открыто отношусь к новым задачам и форматам сотрудничества.
Обладаю базовыми навыками программирования на Python и zero-code инструментами, знаком с основами
автоматизации процессов. Стремлюсь применить приобретенные знания на практике, развиваться в сфере
взаимодействия с искусственным интеллектом.
"""


# ----------------------------- Fix A ---------------------------------

def test_fix_a_third_internship_extracted_via_achievement_extractor() -> None:
    """Главный сценарий Fix A: achievement-экстрактор (не structuring) извлекает
    все 3 стажировки. Раньше пункт 3 («ИИ-анализ отзывов…») падал из-за того,
    что trailing «О себе:» вклеивал prose-раздел «О себе» в блок, и
    responsibility-фильтр гасил пункт за «взаимодейств»."""
    service = AchievementExtractionService(enable_legacy_recovery=False)
    drafts, _warnings = service._build_achievement_drafts(PERMINOV_RESUME)

    titles = [d.title for d in drafts]
    assert len(drafts) == 3, f"expected 3 drafts, got {len(drafts)}: {titles}"

    # Пункт 3 реально различим — содержит «анализ»/«отзыв», не склейка с «О себе».
    joined = " ".join(titles).lower()
    assert "анализ" in joined and "отзыв" in joined, titles

    # Ни один title не впитал trailing section-heading.
    for title in titles:
        for leak in ("о себе", "о себе:", "дополнительные сведения"):
            assert leak not in title.lower(), f"heading leak: {title!r}"


def test_fix_a_no_fabrication_when_no_internships() -> None:
    """Edge-case: резюме без стажировок/проектов → 0 drafts (без выдумывания,
    «Запрещается выдумывать достижения, создавать фиктивный опыт»)."""
    service = AchievementExtractionService(enable_legacy_recovery=False)
    drafts, _ = service._build_achievement_drafts(
        "Иванов Иван\nПрофессиональные навыки\nPython, SQL\nОПЫТ РАБОТЫ\nООО Ромашка, инженер\n2020 - 2024\n"
    )
    assert drafts == []


# ----------------------------- Fix B ---------------------------------

def _profile(*, summary: str = "", technologies_json: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        headline="",
        summary=summary,
        target_roles_json=[],
        experiences=[],
        achievements=[],
        technologies_json=technologies_json or [],
    )


def test_fix_b_technologies_json_match_when_summary_empty() -> None:
    """Главный сценарий Fix B: профиль GitHub-only (summary пустой, навыки
    ТОЛЬКО в technologies_json) должен матчить must_have с этими языками.
    Раньше technologies_json не попадал в corpus → score 0 даже при полном
    совпадении («гит хаб как не учитывался»)."""
    service = VacancyAnalysisService()
    must_have = ["Python разработка", "JavaScript фронтенд"]

    strengths_no, _, score_no = service._compare_with_profile(
        _profile(summary="", technologies_json=[]),
        [],
        must_have=must_have,
        nice_to_have=[],
    )
    strengths_with, _, score_with = service._compare_with_profile(
        _profile(summary="", technologies_json=["Python", "JavaScript", "TypeScript"]),
        [],
        must_have=must_have,
        nice_to_have=[],
    )

    # Без technologies_json в corpus — совпадать не с чем.
    assert strengths_no == []
    assert score_no == 0 or score_no is None
    # С technologies_json — Python/JavaScript матчатся, score > 0.
    assert score_with is not None and score_with > 0, f"expected >0, got {score_with}"
    assert "Python" in {s["keyword"] for s in strengths_with}


def test_fix_b_technologies_json_does_not_false_positive_on_unrelated() -> None:
    """Нет ложного срабатывания: technologies_json с нерелевантными языками
    не даёт совпадения по must_have с другими технологиями."""
    service = VacancyAnalysisService()
    must_have = ["PHP разработка", "1С администрирование"]

    _, _, score = service._compare_with_profile(
        _profile(summary="", technologies_json=["Python", "JavaScript"]),
        [],
        must_have=must_have,
        nice_to_have=[],
    )
    assert score == 0 or score is None