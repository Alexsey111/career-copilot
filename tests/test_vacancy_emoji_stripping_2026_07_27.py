"""Регрессия #3 (2026-07-27): эмодзи-префиксы hh.ru ломали анализ вакансии.

hh.ru ставит эмодзи перед заголовками секций:
    ✅ Что нужно будет делать
    ✅ Нам важны
    ⭐️ Будет преимуществом
    ✅️ Что мы предлагаем
Без уборки _normalize_heading оставлял эмодзи в начале строки, и
_matches_heading по startswith() не срабатывал — секции обязанностей и
преимуществ тихо пропускались, а в must_have попадал безэмодзи-заголовок
«Ключевые навыки» (Настройка ПО, Аналитическое мышление, Контроль качества ПО, PHP).

Решение (по требованию пользователя): эмодзи вырезаются ОДИН раз на границе
загрузки (text_normalization.strip_emoji применяется в
VacancyImportService._normalize_text, ResumeParserService._normalize_text,
ProfileImportService.import_resume_from_text, GitHub-intake). Downstream
больше не имеет эмодзи-обработки. Эти тесты фиксируют контракт.
"""
from app.domain.text_normalization import strip_emoji
from app.services.vacancy_analysis_service import (
    NICE_TO_HAVE_START_HEADINGS,
    REQUIREMENT_START_HEADINGS,
    STOP_HEADINGS,
    VacancyAnalysisService,
)
from app.services.vacancy_import_service import VacancyImportService

# Фрагмент реальной hh.ru-вакансии Перминова (2026-07-27) с эмодзи-заголовками.
HH_VACANCY_WITH_EMOJI = """Технический ассистент по AI и автоматизации
от 60 000 ₽ за месяц
Опыт работы: не требуется
Стажировка

✅️ Что мы предлагаем
💰 Своевременную оплату труда
Доход обсуждается с итоговым кандидатом.
✈️ Полностью удалённый формат

✅ Что нужно будет делать
— работа с внутренними техническими инструментами компании;
— разработка новых технических решений с помощью ИИ;
— проверка корректности работы ботов, форм, таблиц, сервисов и автоматизаций;
— тестирование новых решений перед внедрением;

✅ Нам важны
— уверенная работа с компьютером, таблицами, документами и сервисами;
— высокий уровень логического мышления;

⭐️ Будет преимуществом
— опыт использования Codex, оркестраторов AI и других нейросетей;
— опыт работы с Google Документами, Таблицами и Формами;

Ключевые навыки
Настройка ПО
Аналитическое мышление
Контроль качества программного обеспечения
PHP
"""


def test_strip_emoji_removes_emoji_prefixed_headings() -> None:
    # Эмодзи-префиксы убраны, текст заголовков сохранён.
    assert strip_emoji("✅ Что нужно будет делать") == " Что нужно будет делать"
    assert strip_emoji("⭐️ Будет преимуществом") == " Будет преимуществом"
    assert strip_emoji("✅️ Что мы предлагаем") == " Что мы предлагаем"
    # Составные эмодзи с ZWJ и variation-селекторами тоже уходят целиком.
    assert strip_emoji("🧠 Обучение за счёт компании") == " Обучение за счёт компании"
    assert strip_emoji("💰 Своевременную оплату труда") == " Своевременную оплату труда"
    # Чистый текст не меняется.
    assert strip_emoji("Ключевые навыки") == "Ключевые навыки"
    assert strip_emoji("Python, Git, LLM, API") == "Python, Git, LLM, API"
    # © ® ™ НЕ вырезаются — это текстовые знаки в названиях компаний.
    assert "®" in strip_emoji("Coca-Cola®")
    assert "™" in strip_emoji("Twitter™")


def test_vacancy_import_normalize_strips_emoji_from_description() -> None:
    service = VacancyImportService()

    normalized = service._normalize_text(HH_VACANCY_WITH_EMOJI)

    # Ни одного эмодзи в сохранённом описании.
    assert "✅" not in normalized
    assert "⭐" not in normalized
    assert "💰" not in normalized
    assert "✈" not in normalized
    assert "🧠" not in normalized
    # Заголовки секций остались читаемым текстом (без эмодзи-префикса).
    assert "Что нужно будет делать" in normalized
    assert "Будет преимуществом" in normalized
    assert "Что мы предлагаем" in normalized
    # hh.ru «Ключевые навыки» тоже на месте (но теперь это НЕ единственный
    # матчитщийся заголовок — требования/преимущества тоже парсятся).
    assert "Ключевые навыки" in normalized


def test_vacancy_analysis_captures_real_sections_after_import_normalize() -> None:
    """Главный регрессионный сценарий: после импорт-нормализации (эмодзи
    убраны) детерминированный анализатор ловит обязанности из «Что нужно
    будет делать» и преимущества из «⭐️ Будет преимуществом», а не только
    hh.ru «Ключевые навыки».
    """
    import_service = VacancyImportService()
    analysis_service = VacancyAnalysisService()

    normalized = import_service._normalize_text(HH_VACANCY_WITH_EMOJI)
    lines = analysis_service._clean_lines(normalized)

    must_have = analysis_service._extract_section_items(
        lines,
        start_headings=REQUIREMENT_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )
    nice_to_have = analysis_service._extract_section_items(
        lines,
        start_headings=NICE_TO_HAVE_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )

    # Реальные обязанности из «Что нужно будет делать» (эмодзи-секция,
    # раньше пропускалась) теперь в must_have.
    must_have_text = " ".join(must_have).lower()
    assert "внутренними техническими инструментами" in must_have_text
    assert "ботов" in must_have_text or "бот" in must_have_text
    assert "тестирование" in must_have_text

    # «⭐️ Будет преимуществом» (эмодзи-секция, раньше пропускалась) теперь
    # даёт nice_to_have с конкретикой (Codex / Google Документы).
    nice_text = " ".join(nice_to_have).lower()
    assert "codex" in nice_text or "google" in nice_text

    # Бэдж-регрессия: hh.ru «Ключевые навыки» больше не доминируют в must_have
    # как единственный источник. Конкретно «PHP» не должен попадать в
    # must_have из блока ключевых навыков, когда есть реальная секция
    # обязанностей (PHP не упоминается в обязанностях).
    assert "php" not in must_have_text


def test_resume_and_github_intake_also_strip_emoji() -> None:
    # Контракт: граница загрузки резюме тоже не пропускает эмодзи.
    from app.services.resume_parser_service import ResumeParserService

    parser = ResumeParserService()
    cleaned = parser._normalize_text("✅ О себе\nЯ Python-разработчик 🐍")
    assert "✅" not in cleaned
    assert "🐍" not in cleaned
    assert "Python-разработчик" in cleaned