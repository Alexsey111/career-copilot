from types import SimpleNamespace

from app.services.interview_question_service import InterviewQuestionService
from app.services.interview_readiness_service import InterviewReadinessService


def test_interview_competency_map_uses_extracted_evidence_signals() -> None:
    service = InterviewQuestionService()
    vacancy = SimpleNamespace(
        title="AI Automation Specialist",
        company="Acme",
        location="Remote",
        description_raw="Need AI workflow, prompt engineering and automation tooling.",
    )
    analysis = SimpleNamespace(
        must_have_json=[{"text": "AI workflow", "weight": 100}],
        strengths_json=[{"keyword": "ChatGPT", "requirement_text": "LLM tooling"}],
        gaps_json=[{"keyword": "no-code", "requirement_text": "automation tooling"}],
        keywords_json=["AI workflow", "prompt engineering", "automation"],
        nice_to_have_json=[],
    )
    evidence = [
        {
            "id": "ev-1",
            "title": "Prompt Engineering",
            "snippet_text": "Used ChatGPT and LLM prompts for AI-assisted workflows.",
            "source_type": "resume_structured",
            "category": "prompt_engineering",
            "skills": ["ChatGPT", "LLM", "prompt engineering"],
            "fact_status": "user_provided",
            "evidence_strength": "medium",
        }
    ]

    competency_map = service.build_competency_map(
        vacancy=vacancy,
        analysis=analysis,
        evidence_snippets=evidence,
    )
    questions = service.build_question_set(
        vacancy=vacancy,
        competency_map=competency_map,
        confirmed_achievements=[],
        weak_areas=[],
        evidence_snippets=evidence,
    )

    assert any(item["key"] == "ai_workflow" for item in competency_map["required_skills"])
    assert any(item["key"] == "chatgpt" for item in competency_map["required_skills"])
    assert any(item["key"] == "chatgpt" for item in competency_map["evidence_competencies"])
    assert all(item["key"] != "prompt_engineering" for item in competency_map["evidence_competencies"])

    evidence_question = next(
        item
        for item in questions
        if item["category"] == "evidence_probe"
        and item["competency_key"] == "chatgpt"
    )
    assert evidence_question["source_type"] == "extracted_evidence"
    assert evidence_question["fact_status"] == "user_provided"
    assert evidence_question["recommended_evidence_ids"] == ["ev-1"]
    assert "ChatGPT" in evidence_question["prompt"]


def test_interview_readiness_counts_user_provided_evidence_bank_items() -> None:
    service = InterviewReadinessService()
    competency_map = {
        "required_skills": [
            {"key": "kubernetes", "label": "Kubernetes"},
            {"key": "prompt_engineering", "label": "prompt engineering"},
        ],
        "seniority_expectations": {"level": "senior"},
        "domain_expectations": ["ml/ai"],
    }
    evidence = [
        {
            "id": "ev-1",
            "title": "Kubernetes rollout",
            "snippet_text": "Owned Kubernetes deployment for an AI service used by 500 users.",
            "source_type": "resume_structured",
            "category": "project",
            "skills": ["Kubernetes", "AI", "ownership"],
            "fact_status": "user_provided",
            "evidence_strength": "medium",
        },
        {
            "id": "ev-2",
            "title": "Prompt Engineering",
            "snippet_text": "Designed prompt engineering workflow for LLM quality checks.",
            "source_type": "resume_structured",
            "category": "prompt_engineering",
            "skills": ["prompt engineering", "LLM"],
            "fact_status": "user_provided",
            "evidence_strength": "medium",
        },
    ]

    weak_areas = service.build_weak_areas(
        competency_map=competency_map,
        confirmed_achievements=[],
        evidence_snippets=evidence,
    )

    messages = {item["message"] for item in weak_areas}
    assert "No confirmed Kubernetes evidence" not in messages
    assert "No confirmed prompt engineering evidence" not in messages
    assert "No leadership examples" not in messages
    assert "No scale metrics" not in messages
    assert "Нет подтверждённого опыта в предметной области вакансии" not in messages


def test_interview_readiness_weak_area_keeps_human_requirement_label() -> None:
    service = InterviewReadinessService()

    weak_areas = service.build_weak_areas(
        competency_map={
            "required_skills": [
                {
                    "key": "adobe_photoshop",
                    "label": "Adobe Photoshop",
                    "source_requirement": (
                        "отличное знание графических редакторов "
                        "(Adobe Photoshop, CorelDRAW)"
                    ),
                }
            ],
            "seniority_expectations": {},
            "domain_expectations": [],
        },
        confirmed_achievements=[],
        evidence_snippets=[],
    )

    assert weak_areas[0]["message"] == "No confirmed Adobe Photoshop evidence"
    assert weak_areas[0]["competency_label"] == "Adobe Photoshop"
    assert weak_areas[0]["source_requirement"] == (
        "отличное знание графических редакторов (Adobe Photoshop, CorelDRAW)"
    )


def test_interview_readiness_domain_warning_is_human_readable() -> None:
    service = InterviewReadinessService()

    weak_areas = service.build_weak_areas(
        competency_map={
            "required_skills": [],
            "seniority_expectations": {},
            "domain_expectations": ["финансовое планирование"],
        },
        confirmed_achievements=[],
        evidence_snippets=[],
    )

    domain_warning = next(
        item for item in weak_areas if item.get("category") == "domain"
    )

    assert domain_warning["message"] == (
        "Нет подтверждённого опыта в предметной области вакансии"
    )
    assert domain_warning["competency_label"] == "Предметная область вакансии"
    assert domain_warning["source_requirement"] == "Предметная область вакансии"


def test_domain_weak_area_is_human_readable() -> None:
    service = InterviewReadinessService()

    weak_areas = service.build_weak_areas(
        competency_map={
            "required_skills": [],
            "domain_expectations": ["закупки", "склад"],
            "seniority_expectations": {"level": "middle"},
        },
        confirmed_achievements=[],
        evidence_snippets=[],
    )

    domain = next(item for item in weak_areas if item["category"] == "domain")

    assert domain["message"] == "Нет подтверждённого опыта в предметной области вакансии"
    assert domain["competency_label"] == "Предметная область вакансии"


def test_domain_tokens_expand_synonyms_and_drop_stopwords() -> None:
    service = InterviewReadinessService()

    tokens = service._domain_tokens(["в области снабжения"])

    assert "области" not in tokens
    assert "в" not in tokens
    assert {"снабжение", "закупки", "поставки", "логистика", "склад"} <= tokens


def test_domain_context_tokens_use_full_competency_map() -> None:
    service = InterviewReadinessService()

    tokens = service._domain_context_tokens(
        competency_map={
            "required_skills": [
                {
                    "label": "Имеете высшее образование",
                    "source_requirement": (
                        "Имеете высшее образование "
                        "(техническое / экономическое / в области снабжения)"
                    ),
                }
            ],
            "domain_expectations": ["в области снабжения"],
        }
    )

    assert "имеете" not in tokens
    assert "образование" not in tokens
    assert "техническое" not in tokens
    assert {"снабжение", "закупки", "поставки", "логистика", "склад"} <= tokens


def test_vacancy_context_match_requires_minimum_overlap() -> None:
    service = InterviewReadinessService()

    tokens = {"снабжение", "закупки", "логистика"}

    assert not service._has_vacancy_context_match(
        evidence_text="",
        vacancy_context_tokens=tokens,
    )
    assert service._has_vacancy_context_match(
        evidence_text="Оптимизировал закупки и логистика.",
        vacancy_context_tokens=tokens,
    )
    assert not service._has_vacancy_context_match(
        evidence_text="Оптимизировал закупки.",
        vacancy_context_tokens=tokens,
    )


def test_partial_skill_evidence_matches_vacancy_context_overlap() -> None:
    service = InterviewReadinessService()

    assert service._has_partial_skill_evidence(
        skill_key="supply_chain",
        skill_label="снабжение",
        evidence_snippets=[
            {
                "fact_status": "partial",
                "title": "Оптимизация закупок",
                "snippet_text": "Оптимизировал закупки и логистика.",
            }
        ],
        vacancy_context_tokens={"снабжение", "закупки", "логистика"},
    )


def test_required_skill_matches_confirmed_evidence_by_vacancy_context() -> None:
    service = InterviewReadinessService()

    weak_areas = service.build_weak_areas(
        competency_map={
            "required_skills": [
                {
                    "key": "снабжение",
                    "label": "снабжение",
                    "source_requirement": (
                        "Имеете опыт работы в сфере МТС, закупок или снабжения "
                        "в строительстве от 3 лет"
                    ),
                }
            ],
            "domain_expectations": [
                "Работа с поставщиками",
                "Контроль поставок материалов и оборудования",
                "Договорная работа",
            ],
            "seniority_expectations": {"level": "middle"},
        },
        confirmed_achievements=[
            {
                "title": "Сократил сроки поставок материалов на 18%",
                "fact_status": "confirmed",
            }
        ],
        evidence_snippets=[],
    )

    assert not any(item["competency_key"] == "снабжение" for item in weak_areas)


def test_readiness_uses_full_vacancy_context_text_for_matching() -> None:
    service = InterviewReadinessService()

    weak_areas = service.build_weak_areas(
        competency_map={
            "required_skills": [
                {
                    "key": "снабжение",
                    "label": "снабжение",
                    "source_requirement": "Имеете высшее образование в области снабжения",
                }
            ],
            "vacancy_context_text": (
                "Работа с поставщиками. Контроль поставок материалов и оборудования. "
                "Закупки проектных материалов. Договорная работа."
            ),
            "domain_expectations": [],
            "seniority_expectations": {"level": "middle"},
        },
        confirmed_achievements=[
            {
                "title": "Сократил сроки поставок материалов на 18%",
                "fact_status": "confirmed",
            }
        ],
        evidence_snippets=[],
    )

    assert not any(item["competency_key"] == "снабжение" for item in weak_areas)


def test_required_skill_matches_confirmed_achievement_by_domain_cluster() -> None:
    service = InterviewReadinessService()

    weak_areas = service.build_weak_areas(
        competency_map={
            "required_skills": [
                {
                    "key": "ремонт_сложных_инженерных_систем",
                    "label": "ремонт сложных инженерных систем",
                }
            ],
            "domain_expectations": [],
            "seniority_expectations": {"level": "middle"},
        },
        confirmed_achievements=[
            {
                "title": "Работал со сложными инженерными системами на объекте",
                "fact_status": "confirmed",
            }
        ],
        evidence_snippets=[],
    )

    assert not any(
        item["competency_key"] == "ремонт_сложных_инженерных_систем"
        for item in weak_areas
    )


def test_required_skill_matches_confirmed_snippet_by_domain_cluster() -> None:
    service = InterviewReadinessService()

    weak_areas = service.build_weak_areas(
        competency_map={
            "required_skills": [
                {
                    "key": "ремонт_сложных_инженерных_систем",
                    "label": "ремонт сложных инженерных систем",
                }
            ],
            "domain_expectations": [],
            "seniority_expectations": {"level": "middle"},
        },
        confirmed_achievements=[],
        evidence_snippets=[
            {
                "title": "Работа со сложными инженерными системами",
                "snippet_text": "Работал со сложными инженерными системами на объекте",
                "fact_status": "confirmed",
            }
        ],
    )

    assert not any(
        item["competency_key"] == "ремонт_сложных_инженерных_систем"
        for item in weak_areas
    )


def test_required_skill_matches_by_domain_cluster_context() -> None:
    service = InterviewReadinessService()

    weak_areas = service.build_weak_areas(
        competency_map={
            "required_skills": [
                {
                    "key": "обслуживание_инженерных_систем",
                    "label": "обслуживание инженерных систем",
                    "source_requirement": "обслуживание инженерных систем",
                }
            ],
            "vacancy_context_text": (
                "Обслуживание и ремонт систем водоснабжения и теплоснабжения. "
                "Сантехническое оборудование."
            ),
            "domain_expectations": [],
            "seniority_expectations": {"level": "middle"},
        },
        confirmed_achievements=[
            {
                "title": "Обслуживание внутренних инженерных систем",
                "fact_status": "confirmed",
                "action": "Монтаж систем водоснабжения и канализации",
            }
        ],
        evidence_snippets=[],
    )

    assert not weak_areas


def test_domain_evidence_matches_synonymic_achievements() -> None:
    service = InterviewReadinessService()

    assert service._has_domain_evidence(
        achievements=[
            {
                "title": "Сократил сроки поставок материалов на 18%",
                "description": "Оптимизировал закупки и логистику склада.",
            }
        ],
        evidence_snippets=[],
        domain_expectations=["в области снабжения"],
    )


def test_domain_evidence_matches_supply_synonyms() -> None:
    service = InterviewReadinessService()

    assert service._has_domain_evidence(
        achievements=[
            {
                "title": "Сократил сроки поставок материалов на 18%",
                "fact_status": "confirmed",
            }
        ],
        evidence_snippets=[],
        domain_expectations=["в области снабжения"],
    )


def test_interview_readiness_roadmap_orders_steps_by_expected_gain() -> None:
    service = InterviewReadinessService()

    roadmap = service._build_readiness_roadmap(
        score=62,
        weak_areas=[
            {
                "category": "metrics",
            },
            {
                "category": "technical",
                "competency_label": "Adobe Photoshop",
            },
            {
                "category": "leadership",
            },
            {
                "category": "domain",
            },
        ],
    )

    assert roadmap.current_score == 62
    assert [step.order for step in roadmap.steps] == [1, 2, 3, 4]
    assert [step.expected_gain for step in roadmap.steps] == [15, 10, 8, 6]
    assert [step.title for step in roadmap.steps] == [
        "Подтвердить опыт Adobe Photoshop",
        "Добавить пример лидерства",
        "Подтвердить опыт в предметной области вакансии",
        "Добавить измеримый результат",
    ]
    assert roadmap.projected_score == 100


def test_interview_readiness_roadmap_has_no_steps_at_full_score() -> None:
    service = InterviewReadinessService()

    roadmap = service._build_readiness_roadmap(
        score=100,
        weak_areas=[],
        questions=[
            {
                "competency_name": "коммуникацию",
                "suggested_answer": {
                    "grounding_status": "insufficient_evidence",
                },
            }
        ],
    )

    assert roadmap.current_score == 100
    assert roadmap.projected_score == 100
    assert roadmap.steps == []


def test_readiness_uses_question_evidence_fallback_when_required_skill_coverage_is_zero() -> None:
    service = InterviewReadinessService()

    readiness = service.build_readiness(
        competency_map={
            "required_skills": [
                {"key": "technical", "label": "техническое"},
            ],
        },
        weak_areas=[],
        evidence_links=[
            {
                "question_id": "q-ownership",
                "question_category": "behavioral",
                "competency_key": "ownership",
            },
            {
                "question_id": "q-project",
                "question_category": "project_deep_dive",
                "competency_key": "project",
            },
        ],
    )

    assert readiness["score"] == 40


def test_readiness_penalizes_weak_answer_quality() -> None:
    service = InterviewReadinessService()

    readiness = service.build_readiness(
        competency_map={
            "required_skills": [
                {"key": "ownership", "label": "ownership"},
            ]
        },
        weak_areas=[],
        evidence_links=[
            {"question_id": "q1", "question_category": "technical", "competency_key": "ownership"},
            {"question_id": "q2"},
            {"question_id": "q3"},
        ],
        questions=[
            {"question_id": "q1", "suggested_answer": {"quality": {"score": 78}}},
            {"question_id": "q2", "suggested_answer": {"quality": {"score": 36}}},
            {"question_id": "q3", "suggested_answer": {"quality": {"score": 44}}},
        ],
    )

    assert readiness["score"] == 60
    assert readiness["ready"] is False
    assert "Есть ответы, которые требуют доработки перед интервью" in readiness["warnings"]


def test_readiness_not_ready_when_any_answer_quality_is_weak() -> None:
    service = InterviewReadinessService()

    readiness = service.build_readiness(
        competency_map={"required_skills": []},
        weak_areas=[],
        evidence_links=[
            {"question_id": "q1"},
            {"question_id": "q2"},
            {"question_id": "q3"},
        ],
        questions=[
            {"question_id": "q1", "suggested_answer": {"quality": {"score": 78}}},
            {"question_id": "q2", "suggested_answer": {"quality": {"score": 36}}},
            {"question_id": "q3", "suggested_answer": {"quality": {"score": 78}}},
        ],
    )

    assert readiness["score"] == 40
    assert readiness["ready"] is False


def test_readiness_cannot_stay_at_100_with_weak_answer_warning() -> None:
    service = InterviewReadinessService()

    readiness = service.build_readiness(
        competency_map={
            "required_skills": [
                {"key": "plumbing", "label": "сантехнические работы"},
            ],
        },
        weak_areas=[],
        evidence_links=[
            {
                "question_id": "q-plumbing",
                "question_category": "technical",
                "competency_key": "plumbing",
            }
        ],
        questions=[
            {
                "question_id": "q-plumbing",
                "suggested_answer": {"quality": {"score": 44}},
            }
        ],
    )

    assert readiness["score"] == 80
    assert readiness["ready"] is False
    assert readiness["warnings"] == [
        "Есть ответы, которые требуют доработки перед интервью"
    ]


def test_readiness_roadmap_includes_questions_without_evidence() -> None:
    service = InterviewReadinessService()

    readiness = service.build_readiness(
        competency_map={
            "required_skills": [
                {"key": "technical", "label": "техническое"},
            ],
        },
        weak_areas=[],
        evidence_links=[
            {
                "question_id": "q-ownership",
                "question_category": "behavioral",
                "competency_key": "ownership",
            },
        ],
        questions=[
            {
                "question_id": "q-technical",
                "category": "technical",
                "competency_name": "техническое",
                "suggested_answer": {
                    "grounding_status": "insufficient_evidence",
                },
            },
            {
                "question_id": "q-ownership",
                "category": "behavioral",
                "competency_name": "ответственность",
                "suggested_answer": {
                    "grounding_status": "partial_evidence",
                },
            },
        ],
    )

    steps = readiness["roadmap"]["steps"]

    assert steps
    assert steps[0]["title"] == "Подготовить подтверждённый пример по теме: техническое"
    assert steps[0]["expected_gain"] == 10


def test_readiness_roadmap_humanizes_question_competency_labels() -> None:
    service = InterviewReadinessService()

    readiness = service.build_readiness(
        competency_map={"required_skills": []},
        weak_areas=[],
        evidence_links=[],
        questions=[
            {
                "question_id": "q-communication",
                "category": "behavioral",
                "competency_name": "коммуникацию",
                "suggested_answer": {
                    "grounding_status": "insufficient_evidence",
                },
            },
        ],
    )

    assert readiness["roadmap"]["steps"][0]["title"] == (
        "Подготовить подтверждённый пример по теме: коммуникация"
    )


def test_requirement_label_normalization_filters_generic_labels() -> None:
    service = InterviewQuestionService()

    assert service._normalize_requirement_labels("техническое") == []
    assert service._normalize_requirement_labels("навыки") == []
    assert service._normalize_requirement_labels("Adobe Photoshop") == ["Adobe Photoshop"]
