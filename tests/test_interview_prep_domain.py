from types import SimpleNamespace

from app.domain.interview_prep import infer_domain_expectations, infer_domain_focus_areas


def test_infer_domain_expectations_detects_design_branding() -> None:
    vacancy = SimpleNamespace(
        title="Графический дизайнер",
        company="Test",
        location="",
        description_raw=(
            "Отличное знание графических редакторов Adobe Photoshop, CorelDRAW. "
            "Подготовка макетов к печати, фирменный стиль, брендинг."
        ),
    )
    analysis = SimpleNamespace(
        keywords_json=[],
        must_have_json=[
            {"text": "Adobe Photoshop"},
            {"text": "CorelDRAW"},
            {"text": "подготовка макетов к печати"},
        ],
        nice_to_have_json=[],
        gaps_json=[],
        strengths_json=[],
    )

    assert "design / branding" in infer_domain_expectations(vacancy, analysis)


def test_infer_domain_expectations_uses_non_it_fallback() -> None:
    vacancy = SimpleNamespace(
        title="Специалист",
        company="Test",
        location="",
        description_raw="Работа с документами и клиентами.",
    )
    analysis = SimpleNamespace(
        keywords_json=[],
        must_have_json=[],
        nice_to_have_json=[],
        gaps_json=[],
        strengths_json=[],
    )

    assert infer_domain_expectations(vacancy, analysis) == [
        "general professional delivery"
    ]


def test_infer_domain_focus_areas_uses_vacancy_requirements_without_profession_map() -> None:
    vacancy = SimpleNamespace(
        title="Графический дизайнер",
        company="Test",
        location="",
        description_raw="",
    )
    analysis = SimpleNamespace(
        keywords_json=["фирменный стиль"],
        must_have_json=[
            {"text": "Adobe Photoshop"},
            {"text": "CorelDRAW"},
        ],
        strengths_json=[
            {"keyword": "подготовка макетов к печати"},
        ],
        gaps_json=[],
        nice_to_have_json=[],
    )

    assert infer_domain_focus_areas(vacancy, analysis) == [
        "Adobe Photoshop",
        "CorelDRAW",
        "подготовка макетов к печати",
        "фирменный стиль",
    ]
