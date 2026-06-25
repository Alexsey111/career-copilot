from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.services.cover_letter_generation_service import CoverLetterGenerationService
from app.services.interview_question_service import InterviewQuestionService
from app.services.interview_readiness_service import InterviewReadinessService
from app.services.resume_generation_service import ResumeGenerationService


def _vacancy(title: str, description: str = ""):
    return SimpleNamespace(
        title=title,
        company="Test Company",
        location="",
        description_raw=description,
    )


def _analysis(
    *,
    must_have: list[str],
    strengths: list[str],
    gaps: list[str] | None = None,
    keywords: list[str] | None = None,
):
    return SimpleNamespace(
        must_have_json=[{"text": item, "keyword": item} for item in must_have],
        nice_to_have_json=[],
        strengths_json=[{"keyword": item, "scope": "must_have"} for item in strengths],
        gaps_json=[{"keyword": item, "scope": "must_have"} for item in (gaps or [])],
        keywords_json=keywords or [*must_have, *strengths],
        match_score=75,
    )


@pytest.mark.parametrize(
    "case",
    [
        {
            "name": "lawyer",
            "vacancy_title": "Юрист",
            "profile_summary": "Гражданское право, Договорное право, Арбитраж, Документооборот",
            "experience": "Подготовка договоров\nСудебное сопровождение\nПретензионная работа",
            "achievement": "Подготовила более 250 договоров",
            "must_have": [
                "знание профильного законодательства",
                "нормотворческая деятельность",
                "официально-деловой стиль",
                "юриспруденция",
            ],
            "strengths": ["Договорное право", "Документооборот"],
            "gaps": ["коммуникация"],
            "expected_domain": "юриспруденция",
            "forbidden_question_parts": ["Расскажите про юриспруденцию"],
            "forbidden_cover_parts": ["организации закупок", "контроле поставок"],
        },
        {
            "name": "accountant",
            "vacancy_title": "Бухгалтер",
            "profile_summary": "1С:Бухгалтерия, НДС, Первичная документация, Сверка взаиморасчётов",
            "experience": "Ведение первичной документации\nСверка взаиморасчётов\nПодготовка отчетности",
            "achievement": "Сократила количество ошибок в первичных документах",
            "must_have": [
                "ведение первичной документации",
                "сверка взаиморасчетов",
                "работа в 1С",
                "бухгалтерия",
            ],
            "strengths": ["Первичная документация", "1С:Бухгалтерия"],
            "gaps": ["коммуникация"],
            "expected_domain": "бухгалтерия",
            "forbidden_question_parts": ["Расскажите про бухгалтерию"],
            "forbidden_cover_parts": ["организации закупок", "контроле поставок"],
        },
        {
            "name": "plumber",
            "vacancy_title": "Сантехник",
            "profile_summary": "Монтаж систем водоснабжения, Ремонт трубопроводов, Обслуживание оборудования",
            "experience": "Монтаж систем водоснабжения и канализации\nЗамена трубопроводов\nУстранение аварийных ситуаций",
            "achievement": "Устранил аварийные ситуации на инженерных системах",
            "must_have": [
                "обслуживание инженерных систем",
                "диагностика неисправностей",
                "работа с инструментом",
                "сантехника",
            ],
            "strengths": ["Монтаж систем водоснабжения", "Обслуживание оборудования"],
            "gaps": ["коммуникация"],
            "expected_domain": "сантехника",
            "forbidden_question_parts": ["Расскажите про сантехнику"],
            "forbidden_cover_parts": ["организации закупок", "снижении затрат на снабжение"],
        },
        {
            "name": "designer",
            "vacancy_title": "Графический дизайнер",
            "profile_summary": "Adobe Photoshop, Figma, CorelDRAW, Подготовка макетов к печати, Брендинг",
            "experience": "Разработка рекламных материалов\nСоздание фирменного стиля\nПодготовка макетов к печати",
            "achievement": "Разработала новый фирменный стиль компании",
            "must_have": [
                "Adobe Photoshop",
                "CorelDRAW",
                "подготовка макетов к печати",
                "дизайн",
            ],
            "strengths": ["Adobe Photoshop", "CorelDRAW"],
            "gaps": ["коммуникация"],
            "expected_domain": "дизайн",
            "forbidden_question_parts": ["Расскажите про дизайн"],
            "forbidden_cover_parts": ["организации закупок", "снижении затрат на снабжение"],
        },
        {
            "name": "backend",
            "vacancy_title": "Backend Developer",
            "profile_summary": "Python, FastAPI, PostgreSQL, Docker, Git",
            "experience": "Разработка REST API\nРабота с PostgreSQL\nНастройка Docker окружения",
            "achievement": "Разработал REST API на FastAPI",
            "must_have": [
                "Python",
                "FastAPI",
                "PostgreSQL",
                "backend",
            ],
            "strengths": ["Python", "FastAPI"],
            "gaps": ["Kubernetes"],
            "expected_domain": None,
            "forbidden_question_parts": ["Расскажите про backend"],
            "forbidden_cover_parts": ["организации закупок", "контроле поставок"],
        },
    ],
    ids=lambda case: case["name"],
)
def test_multi_domain_pipeline_invariants(case: dict[str, Any]) -> None:
    resume_service = ResumeGenerationService()
    cover_service = CoverLetterGenerationService()
    question_service = InterviewQuestionService()
    readiness_service = InterviewReadinessService()

    vacancy = _vacancy(case["vacancy_title"])
    analysis = _analysis(
        must_have=case["must_have"],
        strengths=case["strengths"],
        gaps=case["gaps"],
    )
    profile = SimpleNamespace(
        full_name="Test Candidate",
        headline=case["vacancy_title"],
        location="",
        target_roles_json=[case["vacancy_title"]],
        summary=case["profile_summary"],
        experiences=[
            SimpleNamespace(
                company="Test Company",
                role=case["vacancy_title"],
                start_date=None,
                end_date=None,
                description_raw=case["experience"],
            )
        ],
        achievements=[
            SimpleNamespace(
                id="ach-1",
                title=case["achievement"],
                situation=None,
                task=None,
                action=case["achievement"],
                result=case["achievement"],
                metric_text=None,
                evidence_note="test fixture",
                fact_status="confirmed",
                skills_json=case["strengths"],
            )
        ],
    )

    matched_keywords, missing_keywords = resume_service._extract_match_keywords_from_analysis(
        strengths_json=analysis.strengths_json,
        gaps_json=analysis.gaps_json,
    )
    raw_skills = resume_service._extract_skills_from_profile_or_raw_text(
        profile_summary=profile.summary,
        raw_text="",
    )
    experience_items = resume_service._build_experience_items(profile)
    capability_skills = resume_service._extract_capability_skills_from_experience(
        experience_items,
    )
    selected_skills = resume_service._select_resume_skills(
        raw_skills=[*capability_skills, *raw_skills],
        matched_keywords=matched_keywords,
    )
    confirmed_achievements = resume_service._get_confirmed_achievements(
        profile.achievements
    )
    selected_achievements = resume_service._select_relevant_achievements(
        confirmed_achievements,
        matched_keywords,
    )

    assert selected_skills
    assert confirmed_achievements
    assert all(item["fact_status"] == "confirmed" for item in selected_achievements)

    closing = cover_service._build_closing(
        vacancy_title=vacancy.title,
        company=vacancy.company,
        candidate_experiences=profile.experiences,
        selected_skills=selected_skills,
        matched_keywords=matched_keywords,
    )
    closing_lower = closing.lower()

    for forbidden in case["forbidden_cover_parts"]:
        assert forbidden not in closing_lower

    evidence_snippets = [
        {
            "id": "ach-1",
            "title": case["achievement"],
            "snippet_text": case["achievement"],
            "source_type": "manual",
            "skills": case["strengths"],
            "fact_status": "confirmed",
            "evidence_strength": "medium",
            "star_summary": {
                "action": case["achievement"],
                "result": case["achievement"],
            },
        }
    ]

    competency_map = question_service.build_competency_map(
        vacancy=vacancy,
        analysis=analysis,
        evidence_snippets=evidence_snippets,
    )

    domain_labels = [
        item["label"]
        for item in competency_map.get("domain_requirements") or []
    ]
    required_labels = [
        item["label"]
        for item in competency_map.get("required_skills") or []
    ]

    if case["expected_domain"] is None:
        assert domain_labels == []
    else:
        assert case["expected_domain"] in domain_labels
        assert case["expected_domain"] not in required_labels

    weak_areas = readiness_service.build_weak_areas(
        competency_map=competency_map,
        confirmed_achievements=confirmed_achievements,
        evidence_snippets=evidence_snippets,
    )
    questions = question_service.build_question_set(
        vacancy=vacancy,
        competency_map=competency_map,
        confirmed_achievements=confirmed_achievements,
        weak_areas=weak_areas,
        evidence_snippets=evidence_snippets,
    )
    evidence_links = question_service.build_evidence_links(
        questions=questions,
        confirmed_achievements=confirmed_achievements,
        evidence_snippets=evidence_snippets,
        competency_map=competency_map,
    )
    readiness = readiness_service.build_readiness(
        competency_map=competency_map,
        weak_areas=weak_areas,
        evidence_links=evidence_links,
        questions=questions,
    )

    prompts = [question["prompt"] for question in questions]

    assert questions
    assert any(question["category"] == "technical" for question in questions)
    assert any(question["category"] == "behavioral" for question in questions)

    for forbidden in case["forbidden_question_parts"]:
        assert not any(forbidden in prompt for prompt in prompts)

    assert not any(
        question.get("competency_name") == case["expected_domain"]
        for question in questions
        if question.get("category") == "technical"
    )

    assert readiness["score"] is not None
    assert readiness["roadmap"]
    assert "explanation" in readiness
    assert set(readiness["explanation"]) == {
        "summary",
        "positive_factors",
        "negative_factors",
        "next_best_actions",
    }
