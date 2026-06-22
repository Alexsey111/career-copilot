from types import SimpleNamespace

from app.services.interview_question_service import InterviewQuestionService


def test_requirement_items_extract_tools_from_broad_vacancy_requirement() -> None:
    service = InterviewQuestionService()

    competency_map = service.build_competency_map(
        vacancy=SimpleNamespace(title="Графический дизайнер"),
        analysis=SimpleNamespace(
            must_have_json=[
                {
                    "text": (
                        "отличное знание графических редакторов "
                        "(Adobe Photoshop, CorelDRAW)"
                    )
                }
            ],
            strengths_json=[],
            gaps_json=[],
            keywords_json=[],
            nice_to_have_json=[],
        ),
        evidence_snippets=[],
    )

    labels = [item["label"] for item in competency_map["required_skills"]]

    assert labels == ["Adobe Photoshop", "CorelDRAW"]


def test_technical_questions_use_normalized_tool_labels() -> None:
    service = InterviewQuestionService()

    questions = service.build_question_set(
        vacancy=SimpleNamespace(title="Графический дизайнер"),
        competency_map={
            "required_skills": [
                {"key": "adobe_photoshop", "label": "Adobe Photoshop"},
                {"key": "coreldraw", "label": "CorelDRAW"},
            ],
            "behavioral_signals": [],
            "evidence_competencies": [],
            "seniority_expectations": {},
        },
        confirmed_achievements=[],
        weak_areas=[],
        evidence_snippets=[],
    )

    prompts = [item["prompt"] for item in questions if item["category"] == "technical"]

    assert "Расскажите о вашем опыте работы в Adobe Photoshop." in prompts
    assert "Расскажите о вашем опыте работы в CorelDRAW." in prompts


def test_evidence_competencies_are_filtered_by_vacancy_requirements() -> None:
    service = InterviewQuestionService()

    competencies = service._extract_evidence_competencies(
        [
            {
                "id": "ev-1",
                "source_type": "resume_structured",
                "category": "technologies",
                "skills": ["Adobe Photoshop", "Git", "computer vision"],
            }
        ],
        vacancy_competencies=[
            {
                "key": "adobe_photoshop",
                "label": "Adobe Photoshop",
            }
        ],
    )

    assert competencies == []


def test_evidence_competencies_skip_aggregated_technology_stack() -> None:
    service = InterviewQuestionService()

    competencies = service._extract_evidence_competencies(
        [
            {
                "id": "ev-tech",
                "title": "Technology stack from resume",
                "source_type": "resume_structured",
                "category": "technologies",
                "skills": [
                    "computer vision",
                    "Git",
                    "Adobe Photoshop",
                    "CorelDRAW",
                ],
                "fact_status": "user_provided",
            }
        ],
        vacancy_competencies=[
            {
                "key": "adobe_photoshop",
                "label": "Adobe Photoshop",
            }
        ],
    )

    assert competencies == []


def test_evidence_ranking_adds_match_confidence_and_human_reason() -> None:
    service = InterviewQuestionService()

    ranked = service._rank_evidence_items_for_question(
        question={
            "category": "technical",
            "prompt": "Расскажите про Adobe Photoshop",
            "competency_key": "adobe_photoshop",
            "competency_name": "Adobe Photoshop",
        },
        evidence_items=[
            {
                "id": "ev-1",
                "title": "Работа в Adobe Photoshop",
                "fact_status": "confirmed",
                "snippet_text": "Adobe Photoshop подготовка макетов",
                "skills": ["Adobe Photoshop"],
            }
        ],
    )

    assert ranked[0]["match_confidence"] == "high"
    assert ranked[0]["match_type"] in {"exact_requirement", "keyword_overlap"}
    assert "token matches" not in ranked[0]["reason"]
    assert "Факт подтверждён" in ranked[0]["reason"]


def test_evidence_ranking_skips_aggregated_technology_stack() -> None:
    service = InterviewQuestionService()

    ranked = service._rank_evidence_items_for_question(
        question={
            "category": "technical",
            "prompt": "Расскажите про Adobe Photoshop",
            "competency_key": "adobe_photoshop",
            "competency_name": "Adobe Photoshop",
        },
        evidence_items=[
            {
                "id": "ev-tech",
                "title": "Technology stack from resume",
                "source_type": "resume_structured",
                "category": "technologies",
                "fact_status": "user_provided",
                "snippet_text": "computer vision Git Adobe Photoshop CorelDRAW",
                "skills": ["Adobe Photoshop", "Git"],
            },
            {
                "id": "ev-real",
                "title": "Подготовка макетов в Adobe Photoshop",
                "source_type": "resume_structured",
                "category": "achievement",
                "fact_status": "confirmed",
                "snippet_text": "Adobe Photoshop подготовка макетов",
                "skills": ["Adobe Photoshop"],
            },
        ],
    )

    assert [item["achievement_id"] for item in ranked] == ["ev-real"]


def test_gap_risk_question_uses_requirement_as_competency_name() -> None:
    service = InterviewQuestionService()

    questions = service.build_question_set(
        vacancy=SimpleNamespace(title="Графический дизайнер"),
        competency_map={
            "required_skills": [],
            "behavioral_signals": [],
            "evidence_competencies": [],
            "seniority_expectations": {},
        },
        confirmed_achievements=[],
        weak_areas=[
            {
                "message": "No confirmed Adobe Photoshop evidence",
                "category": "technical",
                "competency_key": "adobe_photoshop",
                "source_requirement": "Adobe Photoshop",
            }
        ],
        evidence_snippets=[],
    )

    question = questions[0]

    assert question["category"] == "gap-risk"
    assert question["competency_name"] == "Adobe Photoshop"


def test_behavioral_question_does_not_use_weak_random_evidence_match() -> None:
    service = InterviewQuestionService()

    questions = service.build_question_set(
        vacancy=SimpleNamespace(title="Графический дизайнер"),
        competency_map={
            "required_skills": [],
            "behavioral_signals": ["ownership"],
            "evidence_competencies": [],
            "seniority_expectations": {},
        },
        confirmed_achievements=[],
        weak_areas=[],
        evidence_snippets=[
            {
                "id": "ev-1",
                "title": "Подготовила 200 рекламных материалов",
                "snippet_text": "Подготовила рекламные материалы и макеты для печати",
                "fact_status": "confirmed",
                "skills": ["Adobe Photoshop"],
            }
        ],
    )

    behavioral_question = next(
        item for item in questions if item["category"] == "behavioral"
    )

    assert behavioral_question["recommended_evidence"] == []
    assert behavioral_question["recommended_evidence_ids"] == []
