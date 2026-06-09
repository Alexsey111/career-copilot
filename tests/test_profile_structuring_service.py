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
