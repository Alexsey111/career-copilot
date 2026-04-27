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
