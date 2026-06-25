from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services.interview_question_service import InterviewQuestionService


def _analysis(
    *,
    must_have: list[dict[str, Any]],
    strengths: list[dict[str, Any]] | None = None,
    gaps: list[dict[str, Any]] | None = None,
    keywords: list[str] | None = None,
):
    return SimpleNamespace(
        must_have_json=must_have,
        strengths_json=strengths or [],
        gaps_json=gaps or [],
        nice_to_have_json=[],
        keywords_json=keywords or [],
    )


def _vacancy(*, title: str, description: str = ""):
    return SimpleNamespace(
        title=title,
        company="Test",
        location="",
        description_raw=description,
    )


@pytest.mark.parametrize(
    "case",
    [
        {
            "name": "lawyer",
            "title": "Главный специалист-юрист",
            "must_have": [
                {"text": "знание профильного законодательства"},
                {"text": "нормотворческая деятельность"},
                {"text": "официально-деловой стиль"},
                {"text": "юриспруденция"},
            ],
            "expected_domain": "юриспруденция",
            "forbidden_prompts": [
                "Расскажите про юриспруденцию",
                "Расскажите о практическом опыте по направлению «юриспруденция»",
            ],
        },
        {
            "name": "accountant",
            "title": "Бухгалтер",
            "must_have": [
                {"text": "ведение первичной документации"},
                {"text": "сверка взаиморасчетов"},
                {"text": "работа в 1С"},
                {"text": "бухгалтерия"},
            ],
            "expected_domain": "бухгалтерия",
            "forbidden_prompts": [
                "Расскажите про бухгалтерию",
                "Расскажите о практическом опыте по направлению «бухгалтерия»",
            ],
        },
        {
            "name": "plumber",
            "title": "Сантехник",
            "must_have": [
                {"text": "обслуживание инженерных систем"},
                {"text": "диагностика неисправностей"},
                {"text": "работа с инструментом"},
                {"text": "сантехника"},
            ],
            "expected_domain": "сантехника",
            "forbidden_prompts": [
                "Расскажите про сантехнику",
                "Расскажите о практическом опыте по направлению «сантехника»",
            ],
        },
        {
            "name": "designer",
            "title": "Графический дизайнер",
            "must_have": [
                {"text": "Adobe Photoshop"},
                {"text": "CorelDRAW"},
                {"text": "подготовка макетов к печати"},
                {"text": "дизайн"},
            ],
            "expected_domain": "дизайн",
            "forbidden_prompts": [
                "Расскажите про дизайн",
                "Расскажите о практическом опыте по направлению «дизайн»",
            ],
        },
    ],
    ids=lambda item: item["name"],
)
def test_domain_labels_are_not_used_as_technical_questions(case: dict[str, Any]) -> None:
    service = InterviewQuestionService()

    competency_map = service.build_competency_map(
        vacancy=_vacancy(title=case["title"]),
        analysis=_analysis(must_have=case["must_have"]),
        evidence_snippets=[],
    )

    domain_labels = [
        item["label"]
        for item in competency_map["domain_requirements"]
    ]
    required_skill_labels = [
        item["label"]
        for item in competency_map["required_skills"]
    ]

    assert case["expected_domain"] in domain_labels
    assert case["expected_domain"] not in required_skill_labels

    questions = service.build_question_set(
        vacancy=_vacancy(title=case["title"]),
        competency_map=competency_map,
        confirmed_achievements=[],
        weak_areas=[],
        evidence_snippets=[],
    )

    prompts = [question["prompt"] for question in questions]

    for forbidden in case["forbidden_prompts"]:
        assert forbidden not in prompts

    assert all(
        question["competency_name"] != case["expected_domain"]
        for question in questions
        if question["category"] == "technical"
    )


def test_cross_domain_generalization_keeps_core_contract() -> None:
    service = InterviewQuestionService()

    vacancy = _vacancy(
        title="Редкая операционная роль",
        description=(
            "Нужен специалист для контроля процессов, работы с документами, "
            "коммуникации с подрядчиками и подготовки отчетности."
        ),
    )
    analysis = _analysis(
        must_have=[
            {"text": "контроль процессов"},
            {"text": "работа с документами"},
            {"text": "подготовка отчетности"},
        ],
        keywords=["документы", "отчетность", "подрядчики"],
    )

    competency_map = service.build_competency_map(
        vacancy=vacancy,
        analysis=analysis,
        evidence_snippets=[],
    )

    assert competency_map["required_skills"]
    assert competency_map["behavioral_signals"]
    assert competency_map["seniority_expectations"]
    assert "domain_requirements" in competency_map
    assert "domain_focus_areas" in competency_map

    questions = service.build_question_set(
        vacancy=vacancy,
        competency_map=competency_map,
        confirmed_achievements=[],
        weak_areas=[],
        evidence_snippets=[],
    )

    assert questions
    assert any(question["category"] == "technical" for question in questions)
    assert any(question["category"] == "behavioral" for question in questions)