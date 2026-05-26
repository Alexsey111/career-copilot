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

    assert "Автоматизированный ИИ-контроль качества" in evidence_by_title
    assert evidence_by_title["Автоматизированный ИИ-контроль качества"].category == "automation"
    assert {"automation", "computer vision"}.issubset(
        set(evidence_by_title["Автоматизированный ИИ-контроль качества"].skills)
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
