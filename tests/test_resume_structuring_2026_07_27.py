"""Регрессия #2 (2026-07-27): детерминированный экстрактор резюме криво
парсил формат Перминова.

Баги (все — детерминированные эвристики, БЕЗ LLM; LLM у нас только NLG-слой
поверх проанализированных документов):

#2d — манглинг заголовков стажировок. Нумерованный блок «Прошел 3 стажировки:
1.… 2.… 3.…» под «Дополнительные сведения». Пункт 3 заканчивался на
``» О себе:`` — inline trailing section-heading «О СЕБЕ» протекал в title
(iam signal получал имя вроде «...О себе:»). Фикс: ``_strip_trailing_section_
heading`` обрезает trailing heading, сохраняя prefix.

#2b — fallback достижений. В резюме нет явной секции достижений, но 3
стажировки = реальные проекты. Без fallback ``draft.achievements`` был пуст.
Фикс: если achievements пусты, собираем их из project/internship-сигналов
(без выдумывания — title = title исходного сигнала).

#2c — дедуп образования. Ползунов задваивался (regex «им.» vs «имени» давал
разные норм-формы). Фикс: ``_education_institution_root`` + ``_dedupe_
education_strings``.

#2b-edge — резюме БЕЗ стажировок/проектов НЕ должно фабриковать достижения
(проектное правило: «Запрещается выдумывать достижения»).
"""
from app.services.profile_structuring_service import ProfileStructuringService


# Реальный текст резюме Перминова (extraction d139a425, 2026-07-27).
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

# Резюме без стажировок/проектов/достижений — для edge-case #2b (без фабрикации).
PLAIN_RESUME = """Иванов Иван
г. Москва
Профессиональные навыки
Python, SQL, FastAPI
Желаемая должность
Backend Developer
ОПЫТ РАБОТЫ
ООО Ромашка, Backend-разработчик
01.01.2023 - по настоящее время
ОБРАЗОВАНИЕ
МГТУ им. Баумана, Москва инженер
2018 - 2023
О себе:
Отвечаю за сервисы и API.
"""

SECTION_HEADINGS_LEAK = ("О себе", "О СЕБЕ", "Курсы", "ОПЫТ РАБОТЫ", "Образование")


def _titles(signals) -> list[str]:
    return [str(getattr(s, "title", "") or "").strip() for s in signals]


def test_2d_internship_titles_do_not_leak_trailing_section_heading() -> None:
    """Пункт 3 стажировки заканчивался на «» О себе:» — trailing heading
    «О СЕБЕ» не должен попадать в title стажировки/достижения."""
    draft = ProfileStructuringService()._build_draft(
        PERMINOV_RESUME, source_file_kind="resume"
    )

    # Все три стажировки извлечены.
    internship_titles = _titles(draft.internships) + _titles(draft.projects)
    assert len(internship_titles) >= 3

    # Ни один title не содержит trailing section-heading (главный признак #2d).
    for title in internship_titles:
        for leak in SECTION_HEADINGS_LEAK:
            assert leak not in title, f"heading leak in title: {title!r}"

    # Пункт 3 про «ИИ-анализ отзывов» реально различим (не «Prompt Engineering»
    # и не склейка с «О себе»).
    joined = " ".join(internship_titles).lower()
    assert "анализ" in joined or "отзыв" in joined


def test_2b_achievements_fallback_from_internships_when_no_explicit_section() -> None:
    """В резюме нет секции достижений, но 3 стажировки = реальные проекты →
    achievements заполняются fallback-ом из project/internship-сигналов."""
    draft = ProfileStructuringService()._build_draft(
        PERMINOV_RESUME, source_file_kind="resume"
    )

    achievement_titles = _titles(draft.achievements)
    assert len(achievement_titles) >= 2, achievement_titles

    # Без выдумывания: каждый achievement берётся из реального сигнала
    # (совпадает по title с каким-то project/internship-сигналом).
    source_titles = {
        t.casefold() for t in _titles(draft.internships) + _titles(draft.projects) if t
    }
    for at in achievement_titles:
        assert at.casefold() in source_titles, f"fabricated achievement: {at!r}"

    # И без heading-leak в достижениях тоже.
    for at in achievement_titles:
        for leak in SECTION_HEADINGS_LEAK:
            assert leak not in at


def test_2b_no_fabrication_when_resume_has_no_internships_or_projects() -> None:
    """Edge-case: резюме без стажировок/проектов НЕ должно фабриковать
    достижения (проектное правило: «Запрещается выдумывать достижения»)."""
    draft = ProfileStructuringService()._build_draft(
        PLAIN_RESUME, source_file_kind="resume"
    )

    assert draft.internships == []
    assert draft.projects == []
    assert draft.achievements == []


def test_2c_education_dedup_polzunov_not_doubled() -> None:
    """Ползунов задваивался из-за regex «им.» vs «имени» → разные норм-формы.
    После дедупа — ровно 2 вуза (Ползунов + Рязанское), Ползунов встречается
    ровно один раз."""
    draft = ProfileStructuringService()._build_draft(
        PERMINOV_RESUME, source_file_kind="resume"
    )

    education_items = draft.education
    assert len(education_items) == 2, [str(e) for e in education_items]

    polzunov_count = sum(
        1 for e in education_items if "ползунова" in str(e).lower()
    )
    assert polzunov_count == 1, [str(e) for e in education_items]

    # Рязанское училище тоже на месте (не потерялось при дедупе).
    assert any("рязанское" in str(e).lower() for e in education_items)