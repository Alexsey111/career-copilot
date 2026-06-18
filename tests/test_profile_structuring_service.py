from datetime import date

from app.services.resume_parser_service import ResumeParserService
from app.services.profile_structuring_service import ProfileStructuringService


def test_build_draft_extracts_skills_summary_for_profile_matching() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Перминов Алексей
30.11.1972 г.р.
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, Нейросети, API, SQL,
Анализ данных, Tensorflow, Vibe-coding.
Желаемая должность
Prompt Engineering, Data Science, Vibe-coding
ОПЫТ РАБОТЫ
Acme, AI Engineer
01.01.2023 - по настоящее время
"""
    )

    assert draft.summary is not None
    assert "Python" in draft.summary
    assert "LLM" in draft.summary
    assert "SQL" in draft.summary
    assert "Желаемая должность" not in draft.summary


def test_build_draft_extracts_full_name_from_single_line_ru_name() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Перминов Алексей
30.11.1972 г.р.
Профессиональные навыки
Python, FastAPI, SQL
Желаемая должность
Backend Developer
ОПЫТ РАБОТЫ
Acme, AI Engineer
01.01.2023 - по настоящее время
"""
    )

    assert draft.full_name == "Перминов Алексей"
    assert "full_name was not extracted confidently" not in draft.warnings


def test_build_draft_keeps_three_token_ru_full_name() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Викторович Кузнецов
Целевая должность
Сантехник
Опыт работы
ООО «ТехКомСервис»
Слесарь-сантехник
03.2019 — настоящее время
Навыки
Монтаж систем водоснабжения
"""
    )

    assert draft.full_name == "Сергей Викторович Кузнецов"
    assert draft.headline == "Сантехник"
    assert "full_name was not extracted confidently" not in draft.warnings


def test_build_draft_extracts_name_and_role_from_parser_merged_top_line() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Викторович Кузнецов Целевая должность Сантехник Слесарь-сантехник Город Екатеринбург
Опыт работы
ООО «ТехКомСервис» Слесарь-сантехник
03.2019 — настоящее время
Навыки
Монтаж систем водоснабжения Канализация Отопление
Чтение технических схем Сварочные работы Работа с электроинструментом
"""
    )

    assert draft.full_name == "Сергей Викторович Кузнецов"
    assert draft.target_roles
    assert "full_name was not extracted confidently" not in draft.warnings
    assert "target roles were not extracted" not in draft.warnings


def test_resume_parser_keeps_plain_target_heading_separate_from_name() -> None:
    text = ResumeParserService()._normalize_text(
        """
Сергей Викторович Кузнецов
Целевая должность
Сантехник
Слесарь-сантехник
Город
Екатеринбург
Опыт работы
ООО «ТехКомСервис»
Слесарь-сантехник
03.2019 — настоящее время
"""
    )

    lines = text.splitlines()
    assert lines[:6] == [
        "Сергей Викторович Кузнецов",
        "Целевая должность",
        "Сантехник",
        "Слесарь-сантехник",
        "Город",
        "Екатеринбург",
    ]


def test_build_draft_extracts_simple_generic_backend_resume() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Иван Петров
Backend Developer

Опыт:
ООО CloudSoft
Backend Developer
2022–2026

Обязанности:
- Разработка REST API на FastAPI
- Интеграция PostgreSQL
- Docker контейнеризация
- Настройка CI/CD

Достижения:
- Сократил время ответа API на 35%
- Перевёл монолитный сервис на микросервисную архитектуру
- Настроил автоматическое тестирование

Навыки:
Python
FastAPI
PostgreSQL
SQLAlchemy
Docker
Redis
Pytest
Git

Образование:
МГТУ им. Баумана
Прикладная информатика
"""
    )

    assert draft.full_name == "Иван Петров"
    assert draft.target_roles == ["Backend Developer"]
    assert draft.headline == "Backend Developer"
    assert draft.experiences
    assert draft.experiences[0].company == "ООО CloudSoft"
    assert draft.experiences[0].role == "Backend Developer"
    assert "full_name was not extracted confidently" not in draft.warnings
    assert "target roles were not extracted" not in draft.warnings
    assert "work experience section was not parsed" not in draft.warnings


def test_build_draft_warns_on_generated_application_package() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
ЦЕЛЕВАЯ ПОЗИЦИЯ: Senior Prompt Engineer
КРАТКОЕ РЕЗЮМЕ:
Здравствуйте! Прошу рассмотреть мою кандидатуру...
ПИСЬМО: Добрый день, я заинтересован в вакансии.
"""
    )

    assert draft.full_name is None
    assert draft.experiences == []
    assert any(
        "generated application package" in warning
        for warning in draft.warnings
    )


def test_build_draft_allows_source_resume_with_brief_summary_heading() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Викторович Кузнецов
КРАТКОЕ РЕЗЮМЕ
Сантехник с опытом обслуживания внутренних инженерных систем.
ОПЫТ РАБОТЫ
МУП «Горводоканал»
Сантехник
06.2015 — 02.2019
НАВЫКИ
Чтение технических схем
"""
    )

    assert draft.full_name == "Сергей Викторович Кузнецов"
    assert draft.experiences
    assert not any("generated application package" in warning for warning in draft.warnings)


def test_build_draft_extracts_full_name_from_top_lines_fallback() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Целевая должность
Петров Алексей

Сантехник
Опыт работы
ООО «Жилсервис»
Слесарь-сантехник
03.2020 — 08.2022
"""
    )

    assert draft.full_name == "Петров Алексей"
    assert "full_name was not extracted confidently" not in draft.warnings


def test_build_draft_extracts_full_name_from_split_lines() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Перминов
Алексей
30.11.1972 г.р.
Профессиональные навыки
Python, FastAPI, SQL
Желаемая должность
Backend Developer
ОПЫТ РАБОТЫ
Acme, AI Engineer
01.01.2023 - по настоящее время
"""
    )

    assert draft.full_name == "Перминов Алексей"
    assert "full_name was not extracted confidently" not in draft.warnings


def test_build_draft_handles_pdf_layout_with_contacts_before_name_and_noisy_target_roles() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
г.Барнаул, Россия, 656060
ул. Антона Петрова, д.262, кв. 306
(+7) 9039115133
lev.21.06.2005@gmail.com
https://github.com/Alexsey111
Перминов Алексей
30.11.1972 г.р.
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, Нейросети Прошел 3 стажировки по (промптинг), Создание нейроассистентов, Чат-боты, API, SQL,
Анализ данных, Tensorflow, Vibe-coding.
направлению Data Science:
1. Создание ИИ-системы
Желаемая должность
для мониторинга безопасности в Prompt Engineering, Data Science, Vibe-coding пансионатах для
пожилых
ОПЫТ РАБОТЫ
Acme, AI Engineer
01.01.2023 - по настоящее время
"""
    )

    assert draft.full_name == "Перминов Алексей"
    assert "full_name was not extracted confidently" not in draft.warnings
    assert draft.target_roles == [
        "Prompt Engineering",
        "Data Science",
        "Vibe-coding",
    ]
    assert draft.headline == "Prompt Engineering, Data Science, Vibe-coding"


def test_build_draft_does_not_leak_pdf_experience_role_into_target_roles() -> None:
    from app.services.resume_parser_service import ResumeParserService

    normalized = ResumeParserService()._normalize_text(
        """
Перминов Алексей
30.11.1972 г.р.
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, Нейросети, API, SQL,
Анализ данных, Tensorflow, Vibe-coding.
Желаемая должность
Prompt Engineering, Data Science, Vibe-coding
ОПЫТ РАБОТЫ
Acme, AI Engineer
01.01.2023 - по настоящее время
"""
    )

    draft = ProfileStructuringService()._build_draft(normalized)

    assert draft.target_roles == [
        "Prompt Engineering",
        "Data Science",
        "Vibe-coding",
    ]
    assert "AI Engineer" not in draft.target_roles


def test_structured_resume_extraction_v2_finds_ai_automation_and_competency_signals() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Перминов Алексей
Профессиональные навыки
Python, Git, Искусственный интеллект, LLM, ChatGPT, API, SQL,
Анализ данных, Tensorflow, автоматизация workflow.
Желаемая должность
Prompt Engineering, Data Science
Прошел 3 стажировки по направлению Data Science:
1. Создание ИИ-системы
для мониторинга безопасности в пансионатах для пожилых
2. Автоматизированный ИИ-контроль качества
ПВХ оконных изделий по изображениям и видео
3. Prompt Engineering
Создание нейроассистентов, чат-боты, промптинг
Курсы
Python с нуля
"""
    )

    evidence_by_title = {item.title: item for item in draft.evidence_snippets}

    assert "ИИ-система мониторинга безопасности" in evidence_by_title
    assert evidence_by_title["ИИ-система мониторинга безопасности"].category == "ai_project"
    assert "computer vision" in evidence_by_title["ИИ-система мониторинга безопасности"].skills

    assert "ИИ-контроль качества ПВХ изделий" in evidence_by_title
    assert evidence_by_title["ИИ-контроль качества ПВХ изделий"].category == "automation"
    assert {"automation", "computer vision"}.issubset(
        set(evidence_by_title["ИИ-контроль качества ПВХ изделий"].skills)
    )

    assert "Prompt Engineering" in evidence_by_title
    assert evidence_by_title["Prompt Engineering"].category == "prompt_engineering"
    assert {"ChatGPT", "LLM", "prompt engineering"}.intersection(
        set(evidence_by_title["Prompt Engineering"].skills)
    )

    assert {"AI", "LLM", "ChatGPT", "TensorFlow", "Python", "SQL"}.issubset(
        set(draft.technologies)
    )
    assert draft.competency_signals
    assert all(item.fact_status == "user_provided" for item in draft.evidence_snippets)


def test_profile_structuring_exposes_normalized_contribution_layer() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Portfolio

1. Clinic Operations Dashboard
Built a dashboard for appointment load and patient flow metrics.
Stack: SQL, Python.

2. Contract Review Playbook
Prepared reusable legal review checklist and reduced manual review steps.
""",
        source_file_kind="portfolio",
    )

    assert [item.title for item in draft.contribution_signals] == [
        "Clinic Operations Dashboard",
        "Contract Review Playbook",
    ]
    assert all(
        item.source_layer == "normalized_contribution_signal"
        for item in draft.contribution_signals
    )
    assert all(item.category == "portfolio_project" for item in draft.contribution_signals)


def test_profile_structuring_legacy_recovery_can_be_disabled() -> None:
    service = ProfileStructuringService(enable_legacy_recovery=False)

    assert service._recover_private_noisy_ai_signal_title_legacy(
        [
            "Автоматизированный ИИ-контроль качества",
            "ПВХ оконных изделий по изображениям и видео",
        ]
    ) is None


def test_profile_structuring_legacy_education_course_recovery_can_be_disabled() -> None:
    service = ProfileStructuringService(enable_legacy_recovery=False)

    assert service._extract_known_formal_education_lines(
        "Алтайский государственный технический университет имени И.И. Ползунова, Барнаул"
    ) == []

    assert service._extract_known_course_lines(
        "Курсы Python с нуля Университет Зерокодинга 2024"
    ) == []


def test_profile_structuring_legacy_internship_fragment_can_be_disabled() -> None:
    service = ProfileStructuringService(enable_legacy_recovery=False)

    assert (
        service._prefer_internship_layout_fragment(
            "Python с нуля    ИИ-контроль качества ПВХ изделий"
        )
        == "Python с нуля    ИИ-контроль качества ПВХ изделий"
    )


def test_profile_structuring_legacy_formal_education_line_can_be_disabled() -> None:
    service = ProfileStructuringService(enable_legacy_recovery=False)

    assert (
        service._looks_like_formal_education_line(
            "Алтайский государственный технический университет имени И.И. Ползунова"
        )
        is False
    )


def test_profile_structuring_legacy_formal_education_line_detection_can_be_disabled() -> None:
    service = ProfileStructuringService(enable_legacy_recovery=False)

    assert service._looks_like_formal_education_line(
        "Алтайский государственный технический университет имени И.И. Ползунова"
    ) is False


def test_profile_structuring_legacy_resume_layout_noise_detection_can_be_disabled() -> None:
    service = ProfileStructuringService(enable_legacy_recovery=False)

    assert service._looks_like_resume_layout_noise(
        "Алтайский Государственный Медицинский Университет"
    ) is False


def test_profile_structuring_legacy_target_role_noise_can_be_disabled() -> None:
    service = ProfileStructuringService(enable_legacy_recovery=False)

    assert service._looks_like_target_role_noise(
        "для мониторинга безопасности в пансионатах для пожилых"
    ) is False


def test_profile_structuring_legacy_mixed_education_layout_noise_can_be_disabled() -> None:
    service = ProfileStructuringService(enable_legacy_recovery=False)

    assert service._looks_like_mixed_education_layout_noise(
        "прогнозирования развития городской среды"
    ) is False


def test_build_draft_extracts_compact_single_line_resume_preview_format() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Иван Петров Backend Developer Опыт: ООО CloudSoft Backend Developer 2022–2026 Обязанности: - Разработка REST API на FastAPI - Интеграция PostgreSQL - Docker контейнеризация - Настройка CI/CD Достижения: - Сократил время ответа API на 35% - Перевёл монолитный сервис на микросервисную архитектуру - Настроил автоматическое тестирование Навыки: Python FastAPI PostgreSQL SQLAlchemy Docker Redis Pytest Git Образование: МГТУ им. Баумана Прикладная информатика
"""
    )

    assert draft.full_name == "Иван Петров"
    assert draft.target_roles == ["Backend Developer"]
    assert draft.headline == "Backend Developer"
    assert "full_name was not extracted confidently" not in draft.warnings
    assert "target roles were not extracted" not in draft.warnings


def test_build_draft_does_not_extract_education_as_full_name() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Анна Смирнова Project Manager Опыт: ООО Digital Solutions Project Manager 2021–2026 Обязанности: - Управление IT-проектами - Координация команды 12 человек Навыки: Agile Scrum Kanban Jira Confluence Stakeholder Management Образование: РАНХиГС Менеджмент
"""
    )

    assert draft.full_name == "Анна Смирнова"
    assert draft.full_name != "РАНХиГС Менеджмент"


def test_profile_structuring_splits_inline_project_management_skills() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Анна Смирнова Project Manager Навыки: Agile Scrum Kanban Jira Confluence Stakeholder Management
"""
    )

    assert "Agile" in draft.technologies
    assert "Scrum" in draft.technologies
    assert "Kanban" in draft.technologies
    assert "Jira" in draft.technologies
    assert "Confluence" in draft.technologies
    assert "Stakeholder Management" in draft.technologies
    assert "Agile Scrum Kanban Jira Confluence Stakeholder Management" not in draft.technologies


def test_profile_structuring_extracts_medical_skills() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов Врач-терапевт

Навыки: Терапия Медицинская документация Клиническая диагностика Электронные медицинские системы
"""
    )

    assert "Терапия" in draft.technologies
    assert "Медицинская документация" in draft.technologies
    assert "Клиническая диагностика" in draft.technologies
    assert "Электронные медицинские системы" in draft.technologies


def test_extract_full_name_does_not_append_medical_role() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов Врач-терапевт

Навыки: Терапия Клиническая диагностика
"""
    )

    assert draft.full_name == "Сергей Кузнецов"
    assert draft.headline == "Врач-терапевт"


def test_profile_structuring_splits_three_token_name_with_hyphenated_role() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов Врач-терапевт Опыт:
Городская клиническая больница No7 Врач-терапевт 2018–2026
Навыки:
Терапия Клиническая диагностика
"""
    )

    assert draft.full_name == "Сергей Кузнецов"
    assert draft.headline == "Врач-терапевт"


def test_profile_structuring_extracts_experience_from_inline_company_role_year_range() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов
Врач-терапевт

Опыт:
Городская клиническая больница No7 Врач-терапевт 2018–2026

Навыки:
Терапия
"""
    )

    assert len(draft.experiences) == 1
    assert draft.experiences[0].company == "Городская клиническая больница No7"
    assert draft.experiences[0].role == "Врач-терапевт"


def test_profile_structuring_extracts_description_raw_from_responsibilities() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов
Врач-терапевт

Опыт:
Городская клиническая больница No7 Врач-терапевт 2018–2026
ОБЯЗАННОСТИ:
- Диагностика пациентов
- Назначение лечения

Навыки:
Терапия
"""
    )

    assert len(draft.experiences) == 1
    assert draft.experiences[0].description_raw is not None
    assert "Диагностика пациентов" in draft.experiences[0].description_raw
    assert "Назначение лечения" in draft.experiences[0].description_raw


def test_profile_structuring_extracts_multiline_experience_blocks() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Ирина Соколова
Бухгалтер

Опыт работы
ООО Альфа
Бухгалтер
02.2021 — 06.2023
Обязанности:
- Ведение первичной бухгалтерской документации
- Работа с актами и счетами
- Сверка взаиморасчётов с контрагентами

Достижения:
- Снизила количество ошибок в первичных документах

ООО Бета
Старший бухгалтер
07.2023 — настоящее время
Обязанности:
- Контроль первичной документации
- Подготовка платёжных поручений

Навыки:
1С
Excel
"""
    )

    assert len(draft.experiences) == 2

    first, second = draft.experiences
    assert first.company == "ООО Альфа"
    assert first.role == "Бухгалтер"
    assert first.start_date == date(2021, 2, 1)
    assert first.end_date == date(2023, 6, 30)
    assert first.description_raw is not None
    assert "ведение первичной бухгалтерской документации" in first.description_raw.lower()
    assert "работа с актами и счетами" in first.description_raw.lower()
    assert "сверка взаиморасчётов с контрагентами" in first.description_raw.lower()
    assert "снизила количество ошибок" not in first.description_raw.lower()

    assert second.company == "ООО Бета"
    assert second.role == "Старший бухгалтер"
    assert second.start_date == date(2023, 7, 1)
    assert second.end_date is None
    assert second.description_raw is not None
    assert "контроль первичной документации" in second.description_raw.lower()
    assert "подготовка платёжных поручений" in second.description_raw.lower()


def test_profile_structuring_extracts_plumber_multiline_resume() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Петров Алексей
Сантехник

Опыт работы
ООО «Жилсервис»
Сантехник
03.2020 — 08.2022
Обязанности:
- Обслуживание сантехнических систем
- Устранение аварийных протечек

Достижения:
- Разработал чек-лист профилактического обслуживания оборудования МУП «Горводоканал»
Слесарь-сантехник
09.2022 — настоящее время
Обязанности:
- Ремонт трубопроводов и запорной арматуры
- Профилактическое обслуживание оборудования

Навыки:
Сантехника
Ремонт трубопроводов
"""
    )

    assert draft.full_name == "Петров Алексей"
    assert draft.target_roles == ["Сантехник"]
    assert len(draft.experiences) == 2
    assert draft.experiences[0].company == "ООО «Жилсервис»"
    assert draft.experiences[1].company == "МУП «Горводоканал»"
    assert draft.experiences[1].role == "Слесарь-сантехник"
    assert "Разработал чек-лист" not in draft.experiences[1].company


def test_profile_structuring_extracts_quoted_company_lines_with_month_year_ranges() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Орлов Игорь Сергеевич
Заместитель директора по МТО

Опыт работы
АО «СибирьЭнергоСтрой»
Заместитель директора по МТО
04.2020 — н.в.
Обязанности:
- Организация закупочной деятельности
- Планирование бюджета снабжения
- Ведение переговоров с поставщиками

ООО «РегионСнаб»
Начальник отдела снабжения
01.2016 — 03.2020
Обязанности:
- Контроль поставок
- Договорная работа

Навыки
МТО
Закупки
"""
    )

    assert len(draft.experiences) == 2
    assert draft.experiences[0].company == "АО «СибирьЭнергоСтрой»"
    assert draft.experiences[0].role == "Заместитель директора по МТО"
    assert draft.experiences[0].start_date == date(2020, 4, 1)
    assert draft.experiences[0].end_date is None
    assert draft.experiences[1].company == "ООО «РегионСнаб»"
    assert draft.experiences[1].role == "Начальник отдела снабжения"
    assert draft.experiences[1].start_date == date(2016, 1, 1)
    assert draft.experiences[1].end_date == date(2020, 3, 31)


def test_multiline_experience_extracts_supply_management_resume() -> None:
    service = ProfileStructuringService()

    text = """
Андрей Николаевич Орлов
Целевая должность
Заместитель директора по материально-техническому обеспечению
Директор по снабжению
Город
Новосибирск
Опыт работы
АО «СибирьЭнергоСтрой»
Заместитель директора по МТО
04.2020 — настоящее время

Обязанности:
Организация закупочной деятельности
Управление складскими запасами
Планирование бюджета снабжения

Достижения:
Снизил затраты на закупки на 15%

ООО «РегионСнаб»
Начальник отдела снабжения
02.2016 — 03.2020

Обязанности:
Поиск поставщиков
Проведение тендеров
Контроль поставок
""".strip()

    draft = service._build_draft(text)

    assert draft.full_name == "Андрей Николаевич Орлов"
    assert draft.target_roles == [
        "Заместитель директора по материально-техническому обеспечению",
        "Директор по снабжению",
    ]
    assert len(draft.experiences) == 2


def test_split_inline_responsibility_items_separates_control_and_budgeting_phrases() -> None:
    service = ProfileStructuringService()

    result = service._split_inline_responsibility_items([
        "Контроль поставок Формирование бюджета закупок",
    ])

    assert result == [
        "Контроль поставок",
        "Формирование бюджета закупок",
    ]


def test_profile_structuring_cleans_worker_resume_experience_skills_and_achievements() -> None:
    raw_text = """
Сергей Викторович Кузнецов
Целевая должность
Сантехник
Слесарь-сантехник
Город
Екатеринбург
Опыт работы
ООО «ТехКомСервис»
Слесарь-сантехник
03.2019 — настоящее время

Обязанности:

Монтаж систем водоснабжения и канализации
Обслуживание сантехнического оборудования
Замена трубопроводов
Устранение аварийных ситуаций
Установка сантехнических приборов
Проведение профилактических осмотров
Работа с технической документацией

Достижения:

Снизил количество аварийных заявок на 20%
Сократил среднее время устранения неисправностей
Разработал чек-лист профилактического обслуживания оборудования
МУП «Горводоканал»
Сантехник
06.2015 — 02.2019

Обязанности:

Обслуживание внутренних инженерных систем
Замена запорной арматуры
Проведение аварийных работ
Участие в капитальном ремонте коммуникаций
Навыки
Монтаж систем водоснабжения
Канализация
Отопление
Ремонт трубопроводов
Сантехническое оборудование
Чтение технических схем
Сварочные работы
Работа с электроинструментом
"""

    parsed = ResumeParserService()._normalize_text(raw_text)
    draft = ProfileStructuringService()._build_draft(parsed)

    assert [(item.role, item.company) for item in draft.experiences] == [
        ("Слесарь-сантехник", "ООО «ТехКомСервис»"),
        ("Сантехник", "МУП «Горводоканал»"),
    ]
    assert draft.experiences[1].description_raw == (
        "Обслуживание внутренних инженерных систем\n"
        "Замена запорной арматуры\n"
        "Проведение аварийных работ\n"
        "Участие в капитальном ремонте коммуникаций"
    )
    assert "Чтение технических схем" in draft.technologies
    assert "Сварочные работы" in draft.technologies
    assert "Работа с электроинструментом" in draft.technologies
    assert "Разработал чек-лист профилактического обслуживания оборудования" in [
        item.title for item in draft.achievements
    ]
    assert all("МУП «Горводоканал»" not in item.title for item in draft.achievements)


def test_build_draft_splits_compact_name_role_before_inline_experience_heading() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов Врач-терапевт Опыт: Городская клиническая больница No7 Врач-терапевт 2018–2026 Навыки: Терапия Медицинская документация Клиническая диагностика Электронные медицинские системы
"""
    )

    assert draft.full_name == "Сергей Кузнецов"
    assert draft.headline == "Врач-терапевт"
    assert draft.target_roles == ["Врач-терапевт"]


def test_profile_structuring_does_not_inject_false_ai_in_medical_resume() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов Врач-терапевт Опыт: Городская клиническая больница No7 Врач-терапевт 2018–2026 Навыки: Терапия Медицинская документация Клиническая диагностика Электронные медицинские системы
"""
    )

    assert "AI" not in draft.technologies
    assert "Терапия" in draft.technologies
    assert "Медицинская документация" in draft.technologies
    assert "Клиническая диагностика" in draft.technologies
    assert "Электронные медицинские системы" in draft.technologies


def test_profile_structuring_does_not_extract_ai_from_medical_diagnostics() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов Врач-терапевт

Навыки: Терапия Клиническая диагностика
"""
    )

    assert "Клиническая диагностика" in draft.technologies
    assert "AI" not in draft.technologies


def test_structured_v2_does_not_reappend_compact_headline_to_full_name() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов Врач-терапевт Опыт:
Городская клиническая больница No7 Врач-терапевт 2018–2026 Обязанности:
- Диагностика пациентов
Навыки:
Терапия Медицинская документация Клиническая диагностика
"""
    )

    assert draft.full_name == "Сергей Кузнецов"
    assert draft.headline == "Врач-терапевт"


def test_profile_structuring_does_not_extract_ai_from_plain_medical_text() -> None:
    service = ProfileStructuringService()

    draft = service._build_draft(
        """
Сергей Кузнецов
Врач-терапевт

Навыки:
Терапия
Клиническая диагностика
"""
    )

    assert "Клиническая диагностика" in draft.technologies
    assert "AI" not in draft.technologies
