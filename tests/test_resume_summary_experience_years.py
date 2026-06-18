"""PR-38: Experience-based Summary — тесты для расчёта стажа в summary."""
from datetime import date

from app.services.resume_generation_service import ResumeGenerationService


def test_resume_summary_uses_experience_years_for_plumber() -> None:
    """PR-38: Сантехник с опытом ~8 лет."""
    service = ResumeGenerationService()

    summary = service._build_vacancy_aligned_summary(
        vacancy_title="сантехник",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {
                "start_date": date(2015, 1, 1),
                "end_date": date(2024, 1, 1),
                "description_raw": (
                    "Монтаж систем водоснабжения\n"
                    "Обслуживание сантехнического оборудования\n"
                    "Замена трубопроводов"
                ),
            },
        ],
        top_alignment_evidence=[],
    )

    assert summary.startswith("Сантехник с опытом более 8 лет в сфере")


def test_resume_summary_for_plumber_uses_seniority_and_specialization() -> None:
    service = ResumeGenerationService()

    summary = service._build_vacancy_aligned_summary(
        vacancy_title="сантехник",
        selected_skills=[],
        selected_achievements=[
            {
                "title": (
                    "Сантехник я занимался устранением аварийных ситуаций "
                    "и разработал чек-лист профилактического обслуживания оборудования"
                )
            }
        ],
        experience_items=[
            {
                "start_date": date(2013, 1, 1),
                "end_date": date(2024, 1, 1),
                "description_raw": (
                    "Монтаж систем водоснабжения и канализации\n"
                    "Обслуживание сантехнического оборудования\n"
                    "Замена трубопроводов"
                ),
            },
        ],
        top_alignment_evidence=[],
    )

    assert summary.startswith(
        "Сантехник с опытом более 10 лет в сфере "
        "обслуживания инженерных систем, ремонта трубопроводов "
        "и устранения аварийных ситуаций."
    )
    assert "За время работы - устранение аварийных ситуаций" in summary
    assert "разработка чек-листа профилактического обслуживания оборудования" in summary
    assert "За время работы сантехник я занимался" not in summary
    assert "монтажом и обслуживания" not in summary


def test_resume_summary_uses_experience_years_for_accountant() -> None:
    """PR-38: Бухгалтер с опытом ~5 лет."""
    service = ResumeGenerationService()

    summary = service._build_vacancy_aligned_summary(
        vacancy_title="бухгалтер",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {
                "start_date": date(2018, 1, 1),
                "end_date": date(2024, 1, 1),
                "description_raw": (
                    "Ведение первичной бухгалтерской документации\n"
                    "Работа с актами и счетами\n"
                    "Сверка взаиморасчетов с контрагентами"
                ),
            },
        ],
        top_alignment_evidence=[],
    )

    assert summary.startswith("Бухгалтер с опытом более 5 лет в сфере")


def test_resume_summary_uses_experience_years_for_lawyer() -> None:
    """PR-38: Юрист с опытом ~8 лет."""
    service = ResumeGenerationService()

    summary = service._build_vacancy_aligned_summary(
        vacancy_title="юрист",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {
                "start_date": date(2016, 1, 1),
                "end_date": date(2024, 1, 1),
                "description_raw": (
                    "Подготовка договоров\n"
                    "Судебное сопровождение\n"
                    "Консультирование клиентов"
                ),
            },
        ],
        top_alignment_evidence=[],
    )

    assert summary.startswith("Юрист с опытом более 8 лет в сфере")


def test_resume_summary_without_dates_does_not_show_years() -> None:
    """PR-38: Если нет дат — показываем просто 'с опытом'."""
    service = ResumeGenerationService()

    summary = service._build_vacancy_aligned_summary(
        vacancy_title="сантехник",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {
                "description_raw": "Монтаж систем водоснабжения",
            },
        ],
        top_alignment_evidence=[],
    )

    assert summary.startswith("Сантехник с опытом")
    assert "лет" not in summary
    assert "года" not in summary
    assert "год" not in summary


def test_resume_calculate_total_experience_years() -> None:
    """PR-38: Проверка метода расчёта стажа."""
    service = ResumeGenerationService()

    # 8 лет (2015-2024)
    years = service._calculate_total_experience_years([
        {"start_date": date(2015, 1, 1), "end_date": date(2024, 1, 1)},
    ])
    assert years == 8

    # 5 лет (2018-2024)
    years = service._calculate_total_experience_years([
        {"start_date": date(2018, 1, 1), "end_date": date(2024, 1, 1)},
    ])
    assert years == 5

    # 8 лет (2016-2024)
    years = service._calculate_total_experience_years([
        {"start_date": date(2016, 1, 1), "end_date": date(2024, 1, 1)},
    ])
    assert years == 8

    # 2 года (2021-2024)
    years = service._calculate_total_experience_years([
        {"start_date": date(2021, 1, 1), "end_date": date(2024, 1, 1)},
    ])
    assert years == 2

    # Несколько мест работы (3 + 5 = 8 лет) — без перекрытия
    years = service._calculate_total_experience_years([
        {"start_date": date(2015, 1, 1), "end_date": date(2018, 1, 1)},
        {"start_date": date(2019, 1, 1), "end_date": date(2024, 1, 1)},
    ])
    assert years == 8

    # Без дат
    years = service._calculate_total_experience_years([
        {"description_raw": "some work"},
    ])
    assert years == 0

    # С незавершённым местом работы (None как end_date)
    years = service._calculate_total_experience_years([
        {"start_date": date(2020, 1, 1), "end_date": None},
    ])
    # Должно считать до текущего года
    assert years >= 4


def test_resume_summary_experience_years_declension() -> None:
    """PR-38: Проверка склонения 'год/года/лет'."""
    from datetime import date
    service = ResumeGenerationService()

    # 2 года (2021-2024)
    summary = service._build_vacancy_aligned_summary(
        vacancy_title="тест",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {"start_date": date(2021, 1, 1), "end_date": date(2024, 1, 1)},
        ],
        top_alignment_evidence=[],
    )
    assert "2 года" in summary

    # 4 года (2019-2024)
    summary = service._build_vacancy_aligned_summary(
        vacancy_title="тест",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {"start_date": date(2019, 1, 1), "end_date": date(2024, 1, 1)},
        ],
        top_alignment_evidence=[],
    )
    assert "4 года" in summary

    # 5 лет (2018-2024)
    summary = service._build_vacancy_aligned_summary(
        vacancy_title="тест",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {"start_date": date(2018, 1, 1), "end_date": date(2024, 1, 1)},
        ],
        top_alignment_evidence=[],
    )
    assert "5 лет" in summary

    # 10 лет (2013-2024) — особое склонение
    summary = service._build_vacancy_aligned_summary(
        vacancy_title="тест",
        selected_skills=[],
        selected_achievements=[],
        experience_items=[
            {"start_date": date(2013, 1, 1), "end_date": date(2024, 1, 1)},
        ],
        top_alignment_evidence=[],
    )
    assert "10 лет" in summary
