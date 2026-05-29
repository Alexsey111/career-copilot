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
    assert {"AI", "computer vision"}.issubset(
        set(evidence_by_title["ИИ-система мониторинга безопасности"].skills)
    )

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
