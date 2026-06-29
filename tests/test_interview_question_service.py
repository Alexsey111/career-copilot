from types import SimpleNamespace

from app.domain.interview_prep import build_competency_key
from app.services.interview_question_service import InterviewQuestionService


def test_build_competency_key_supports_cyrillic() -> None:
    assert build_competency_key("снабжение") == "снабжение"
    assert build_competency_key("в области снабжения") == "в_области_снабжения"
    assert build_competency_key("Adobe Photoshop") == "adobe_photoshop"


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


def test_domain_requirement_is_separated_from_required_skills() -> None:
    service = InterviewQuestionService()

    item = service._extract_requirement_items(
        [{"text": "Сантехника"}],
        source="must_have",
    )[0]

    assert item["type"] == "domain"


def test_build_competency_map_separates_domain_requirements() -> None:
    service = InterviewQuestionService()

    competency_map = service.build_competency_map(
        vacancy=SimpleNamespace(
            title="Сантехник",
            description_raw="Обслуживание инженерных систем.",
        ),
        analysis=SimpleNamespace(
            must_have_json=[
                {"text": "Сантехника"},
                {"text": "обслуживание инженерных систем"},
            ],
            strengths_json=[],
            gaps_json=[],
            keywords_json=[],
            nice_to_have_json=[],
        ),
        evidence_snippets=[],
    )

    assert [item["label"] for item in competency_map["required_skills"]] == [
        "обслуживание инженерных систем"
    ]
    assert [item["label"] for item in competency_map["domain_requirements"]] == [
        "Сантехника"
    ]


def test_requirement_normalization_drops_low_quality_generic_labels() -> None:
    service = InterviewQuestionService()

    assert service._normalize_requirement_labels("техническое") == []
    assert service._normalize_requirement_labels("организационное") == []
    assert service._normalize_requirement_labels("навыки") == []
    assert service._normalize_requirement_labels("экономическое") == []
    assert service._normalize_requirement_labels("юридическое") == []


def test_requirement_normalization_drops_adjectival_descriptors() -> None:
    service = InterviewQuestionService()

    assert service._normalize_requirement_labels("экономическое") == []
    assert service._normalize_requirement_labels("управленческое") == []
    assert service._normalize_requirement_labels("логистическое") == []


def test_requirement_normalization_normalizes_prepositional_phrases() -> None:
    service = InterviewQuestionService()

    assert service._normalize_requirement_labels("в области снабжения") == ["снабжение"]
    assert service._normalize_requirement_labels("в сфере закупок") == ["закупки"]
    assert service._normalize_requirement_labels("в направлении логистики") == ["логистика"]


def test_requirement_normalization_cleans_prepositional_domain_phrase() -> None:
    service = InterviewQuestionService()

    assert service._normalize_requirement_labels("в области снабжения") == ["снабжение"]
    assert service._normalize_requirement_labels("в сфере закупок") == ["закупки"]


def test_requirement_normalization_cleans_parenthesized_domain_phrase() -> None:
    service = InterviewQuestionService()

    assert service._normalize_requirement_labels(
        "Имеете высшее образование (техническое / экономическое / в области снабжения)"
    ) == ["снабжение"]


def test_extract_requirement_items_skips_low_quality_generic_labels() -> None:
    service = InterviewQuestionService()

    items = service._extract_requirement_items(
        [{"text": "техническое"}],
        source="must_have",
    )

    assert items == []


def test_extract_requirement_items_skips_low_quality_adjectival_descriptors() -> None:
    service = InterviewQuestionService()

    items = service._extract_requirement_items(
        [{"text": "экономическое"}],
        source="must_have",
    )

    assert items == []


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


def test_clean_evidence_title_truncates_concatenated_achievement_title() -> None:
    service = InterviewQuestionService()

    assert service._clean_evidence_title(
        "Подготовила более 200 рекламных материалов для федеральных кампаний Участвовала в ребрендинге продуктовой линейки"
    ) == "Подготовила более 200 рекламных материалов для федеральных кампаний"


def test_behavioral_question_does_not_attach_medium_confidence_evidence() -> None:
    service = InterviewQuestionService()

    question = service._build_question(
        category="behavioral",
        prompt="Приведите пример, где вы проявили communication в рабочем проекте.",
        answer_format="STAR",
        competency_key="communication",
        competency_name="communication",
        evidence_candidates=[
            {
                "id": "ev-1",
                "title": "Подготовила более 200 рекламных материалов",
                "fact_status": "confirmed",
                "snippet_text": "Подготовила более 200 рекламных материалов",
                "skills": [],
            }
        ],
    )

    assert question["recommended_evidence"] == []
    assert question["recommended_evidence_ids"] == []


def test_behavioral_filter_rejects_high_confidence_weak_overlap() -> None:
    service = InterviewQuestionService()

    filtered = service._filter_ranked_evidence_for_question(
        category="behavioral",
        ranked=[
            {
                "achievement_id": "ev-1",
                "match_confidence": "high",
                "match_type": "weak_overlap",
            }
        ],
    )

    assert filtered == []


def test_behavioral_question_uses_natural_communication_prompt() -> None:
    service = InterviewQuestionService()

    questions = service.build_question_set(
        vacancy=SimpleNamespace(title="Графический дизайнер"),
        competency_map={
            "required_skills": [],
            "behavioral_signals": ["communication"],
            "evidence_competencies": [],
            "seniority_expectations": {},
        },
        confirmed_achievements=[],
        weak_areas=[],
        evidence_snippets=[],
    )

    behavioral_question = next(
        item for item in questions if item["category"] == "behavioral"
    )

    assert (
        behavioral_question["prompt"]
        == "Расскажите о ситуации, где коммуникация помогла решить рабочую задачу."
    )
    assert "проявили коммуникацию" not in behavioral_question["prompt"]


def test_domain_focus_areas_use_normalized_required_skills_first() -> None:
    service = InterviewQuestionService()

    focus_areas = service._build_domain_focus_areas(
        required_skills=[
            {"key": "adobe_photoshop", "label": "Adobe Photoshop"},
            {"key": "coreldraw", "label": "CorelDRAW"},
        ],
        domain_requirements=[],
        vacancy=None,
        analysis=None,
    )

    assert focus_areas == ["Adobe Photoshop", "CorelDRAW"]


def test_confirmed_single_token_overlap_is_low_confidence() -> None:
    service = InterviewQuestionService()

    confidence = service._evidence_match_confidence(
        score=1.85,
        overlap=1,
        competency_overlap=1,
        evidence={
            "fact_status": "confirmed",
        },
    )

    assert confidence == "low"


def test_prompt_context_overlap_does_not_create_supporting_evidence() -> None:
    service = InterviewQuestionService()

    question = service._build_question(
        category="technical",
        prompt="Расскажите о вашем опыте работы в Adobe Photoshop.",
        answer_format="STAR_or_example",
        competency_key="adobe_photoshop",
        competency_name="Adobe Photoshop",
        evidence_candidates=[
            {
                "id": "ev-1",
                "title": "Участвовала в ребрендинге продуктовой линейки",
                "fact_status": "confirmed",
                "snippet_text": "Участвовала в ребрендинге продуктовой линейки",
                "skills": [],
            }
        ],
    )

    assert question["recommended_evidence"] == []
    assert question["recommended_evidence_ids"] == []


def test_technical_question_does_not_attach_weak_text_match_even_if_confirmed() -> None:
    service = InterviewQuestionService()

    question = service._build_question(
        category="technical",
        prompt="Расскажите о вашем опыте работы в Adobe Photoshop.",
        answer_format="STAR_or_example",
        competency_key="adobe_photoshop",
        competency_name="Adobe Photoshop",
        evidence_candidates=[
            {
                "id": "ev-1",
                "title": "Участвовала в ребрендинге продуктовой линейки",
                "fact_status": "confirmed",
                "snippet_text": "Участвовала в ребрендинге продуктовой линейки",
                "skills": [],
            }
        ],
    )

    assert question["recommended_evidence"] == []
    assert question["recommended_evidence_ids"] == []
    assert question["source_achievement_id"] is None


def test_technical_question_uses_vacancy_context_to_rank_supply_evidence() -> None:
    service = InterviewQuestionService()

    question = service._build_question(
        category="technical",
        prompt="Расскажите о вашем опыте организации снабжения.",
        answer_format="STAR_or_example",
        competency_key="снабжение",
        competency_name="снабжение",
        evidence_candidates=[
            {
                "id": "ev-1",
                "achievement_id": "ev-1",
                "title": "Сократил сроки поставок материалов на 18%",
                "snippet_text": "Сократил сроки поставок материалов на 18%",
                "fact_status": "confirmed",
                "skills": [],
            }
        ],
        vacancy_context_text=(
            "Работа с поставщиками. Контроль поставок материалов и оборудования. "
            "Закупки проектных материалов."
        ),
    )

    assert question["recommended_evidence"]
    assert question["recommended_evidence"][0]["achievement_id"] == "ev-1"
    assert question["recommended_evidence"][0]["match_type"] == "vacancy_context_overlap"


def test_technical_question_uses_stemmed_domain_cluster_overlap() -> None:
    service = InterviewQuestionService()

    question = service._build_question(
        category="technical",
        prompt="Расскажите о ремонте сложных инженерных систем.",
        answer_format="STAR_or_example",
        competency_key="ремонт_сложных_инженерных_систем",
        competency_name="ремонт сложных инженерных систем",
        evidence_candidates=[
            {
                "id": "ev-1",
                "achievement_id": "ev-1",
                "title": "Работал со сложными инженерными системами на объекте",
                "snippet_text": "Работал со сложными инженерными системами на объекте",
                "fact_status": "confirmed",
                "skills": [],
            }
        ],
    )

    assert question["recommended_evidence"]
    assert question["recommended_evidence"][0]["achievement_id"] == "ev-1"
    assert question["recommended_evidence"][0]["match_type"] == "domain_cluster_overlap"
    assert (
        "Связано с предметной областью вакансии"
        in question["recommended_evidence"][0]["reason"]
    )


def test_technical_question_uses_domain_cluster_overlap_for_engineering_systems() -> None:
    service = InterviewQuestionService()

    question = service._build_question(
        category="technical",
        prompt="Расскажите о практическом опыте по направлению «обслуживание инженерных систем».",
        answer_format="STAR_or_example",
        competency_key="обслуживание_инженерных_систем",
        competency_name="обслуживание инженерных систем",
        vacancy_context_text=(
            "Обслуживание и ремонт систем водоснабжения и теплоснабжения. "
            "Проведение профилактических осмотров. Сантехническое оборудование."
        ),
        evidence_candidates=[
            {
                "id": "ev-1",
                "achievement_id": "ev-1",
                "title": "Обслуживание внутренних инженерных систем",
                "snippet_text": (
                    "Монтаж систем водоснабжения и канализации. "
                    "Обслуживание сантехнического оборудования."
                ),
                "fact_status": "confirmed",
                "skills": [],
            }
        ],
    )

    assert question["recommended_evidence"]
    assert question["recommended_evidence"][0]["match_type"] == "domain_cluster_overlap"


def test_engineering_systems_rank_stronger_domain_evidence_first() -> None:
    service = InterviewQuestionService()

    question = service._build_question(
        category="technical",
        prompt="Расскажите о практическом опыте по направлению «обслуживание инженерных систем».",
        answer_format="STAR_or_example",
        competency_key="обслуживание_инженерных_систем",
        competency_name="обслуживание инженерных систем",
        vacancy_context_text=(
            "Обслуживание и ремонт систем водоснабжения и теплоснабжения. "
            "Проведение профилактических осмотров. Сантехническое оборудование."
        ),
        evidence_candidates=[
            {
                "id": "weak",
                "title": "Разработал чек-лист профилактического обслуживания оборудования",
                "snippet_text": "Подготовил чек-лист профилактических осмотров оборудования.",
                "fact_status": "confirmed",
                "skills": [],
            },
            {
                "id": "strong",
                "title": "Обслуживание внутренних инженерных систем",
                "snippet_text": (
                    "Монтаж систем водоснабжения и канализации. "
                    "Обслуживание сантехнического оборудования."
                ),
                "fact_status": "confirmed",
                "skills": ["обслуживание инженерных систем"],
            },
        ],
    )

    assert question["recommended_evidence"]
    assert question["recommended_evidence"][0]["achievement_id"] == "strong"
    assert question["recommended_evidence"][0]["score"] > question["recommended_evidence"][1]["score"]


def test_supply_question_uses_natural_russian_prompt() -> None:
    service = InterviewQuestionService()

    prompt = service._technical_question_prompt(
        skill_label="снабжение",
        vacancy_title="Руководитель отдела снабжения",
    )

    assert prompt == "Расскажите о вашем опыте организации снабжения."


def test_technical_question_cleans_generic_vacancy_word_from_title() -> None:
    service = InterviewQuestionService()

    prompt = service._technical_question_prompt(
        skill_label="обслуживание инженерных систем",
        vacancy_title="Сантехник вакансия",
    )

    assert prompt == (
        "Расскажите о практическом опыте по направлению "
        "«Обслуживание инженерных систем» для позиции «Сантехник»."
    )


def test_technical_question_uses_canonical_question_label() -> None:
    service = InterviewQuestionService()

    prompt = service._technical_question_prompt(
        skill_label="Коммерческие проекты",
        vacancy_title="Project Manager",
    )

    assert prompt == (
        "Расскажите о практическом опыте по направлению "
        "«Опыт управления коммерческими проектами» для позиции «Project Manager»."
    )


def test_vacancy_title_cleaner_handles_prefix_and_extra_whitespace() -> None:
    service = InterviewQuestionService()

    assert service._clean_vacancy_title("  Вакансия: врач  ") == "врач"
    assert service._clean_vacancy_title("Юрист вакансия") == "Юрист"
    assert service._clean_vacancy_title("Бухгалтер") == "Бухгалтер"


def test_evidence_links_use_question_recommendations_as_source_of_truth() -> None:
    service = InterviewQuestionService()

    questions = [
        {
            "question_id": "q-supply",
            "category": "technical",
            "prompt": "Расскажите о вашем опыте организации снабжения.",
            "answer_format": "STAR_or_example",
            "competency_key": "снабжение",
            "competency_name": "снабжение",
            "recommended_evidence_ids": ["ev-1"],
            "recommended_evidence": [
                {
                    "achievement_id": "ev-1",
                    "title": "Сократил сроки поставок материалов на 18%",
                    "score": 4.6,
                    "reason": "Совпадает с контекстом вакансии · Факт подтверждён",
                    "match_type": "vacancy_context_overlap",
                }
            ],
        }
    ]

    links = service.build_evidence_links(
        questions=questions,
        confirmed_achievements=[
            {
                "id": "ev-1",
                "title": "Сократил сроки поставок материалов на 18%",
                "fact_status": "confirmed",
            }
        ],
        evidence_snippets=None,
        competency_map={
            "vacancy_context_text": (
                "Работа с поставщиками. Контроль поставок материалов и оборудования. "
                "Закупки проектных материалов."
            )
        },
    )

    assert links
    assert links[0]["question_id"] == "q-supply"
    assert links[0]["achievement_title"] == "Сократил сроки поставок материалов на 18%"
    assert questions[0]["recommended_evidence"][0]["match_type"] == "vacancy_context_overlap"


def test_evidence_links_do_not_rerank_when_question_has_no_recommendations() -> None:
    service = InterviewQuestionService()
    questions = [
        {
            "question_id": "q-supply",
            "category": "technical",
            "competency_key": "снабжение",
            "recommended_evidence_ids": [],
            "recommended_evidence": [],
        }
    ]

    links = service.build_evidence_links(
        questions=questions,
        confirmed_achievements=[
            {
                "id": "ev-1",
                "title": "Сократил сроки поставок материалов на 18%",
                "fact_status": "confirmed",
            }
        ],
        competency_map={
            "vacancy_context_text": "Контроль поставок и закупки материалов.",
        },
    )

    assert links == []
    assert questions[0]["recommended_evidence"] == []


def test_evidence_links_deduplicate_same_achievement() -> None:
    service = InterviewQuestionService()

    ranked = [
        {
            "achievement_id": "same-id",
            "title": "Сократил сроки поставок материалов на 18%",
            "score": 10,
        },
        {
            "achievement_id": "same-id",
            "title": "Сократил сроки поставок материалов на 18%",
            "score": 9,
        },
    ]

    deduped = service._dedupe_ranked_evidence(ranked)

    assert len(deduped) == 1


def test_evidence_links_do_not_attach_weak_technical_text_match() -> None:
    service = InterviewQuestionService()
    evidence = {
        "id": "ev-1",
        "title": "Участвовала в ребрендинге продуктовой линейки",
        "fact_status": "confirmed",
        "snippet_text": "Участвовала в ребрендинге продуктовой линейки",
        "skills": [],
    }
    question = service._build_question(
        category="technical",
        prompt="Расскажите о вашем опыте работы в Adobe Photoshop.",
        answer_format="STAR_or_example",
        competency_key="adobe_photoshop",
        competency_name="Adobe Photoshop",
        evidence_candidates=[evidence],
    )

    links = service.build_evidence_links(
        questions=[question],
        confirmed_achievements=[],
        evidence_snippets=[evidence],
    )

    assert links == []
    assert question["recommended_evidence"] == []
    assert question["recommended_evidence_ids"] == []
