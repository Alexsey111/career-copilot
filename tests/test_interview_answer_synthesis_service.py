from __future__ import annotations

from app.services.interview_answer_synthesis_service import (
    InterviewAnswerSynthesisService,
)


def test_interview_answer_synthesis_does_not_use_unconfirmed_repository_star_as_ownership() -> None:
    service = InterviewAnswerSynthesisService()

    question = {
        "question_id": "q-fastapi",
        "category": "technical",
        "prompt": "Расскажите о проекте с FastAPI",
        "competency_key": "fastapi",
        "competency_name": "FastAPI",
        "recommended_evidence_ids": ["ev-career-copilot"],
    }
    evidence = {
        "id": "ev-career-copilot",
        "title": "Разработка AI workflow orchestration системы",
        "snippet_text": "FastAPI backend with OpenAI workflow orchestration.",
        "skills": ["FastAPI", "PostgreSQL", "OpenAI", "AI Workflow"],
        "fact_status": "needs_confirmation",
        "candidate_ownership_confidence": "low",
        "requires_confirmation": True,
        "star_summary": {
            "situation": "Нужно было собрать AI Career Copilot workflow.",
            "task": "Спроектировать backend для анализа вакансий и генерации документов.",
            "action": (
                "Спроектировал FastAPI backend, pipeline анализа вакансий, "
                "tailored resume generation и workflow review."
            ),
            "result": "Получился evidence-backed backend/AI workflow experience.",
        },
    }

    answer = service.build_answer(
        question=question,
        evidence_by_id={"ev-career-copilot": evidence},
    )

    assert answer["format"] == "STAR_plus_tradeoffs"
    assert answer["situation"] != "Нужно было собрать AI Career Copilot workflow."
    assert "pipeline анализа вакансий" not in answer["action"]
    assert "tailored resume" not in answer["action"]
    assert "FastAPI" in answer["tech_stack"]
    assert "OpenAI" in answer["tech_stack"]
    assert any("persistence boundaries" in item for item in answer["tradeoffs"])
    assert "Situation:" in answer["draft_text"]
    assert answer["source_evidence_id"] == "ev-career-copilot"
    assert answer["fact_status"] == "needs_confirmation"


def test_interview_answer_synthesis_builds_honest_gap_answer() -> None:
    service = InterviewAnswerSynthesisService()

    answer = service.build_answer(
        question={
            "question_id": "q-gap-kubernetes",
            "category": "gap-risk",
            "prompt": "Как ответить на вопрос о Kubernetes?",
            "competency_key": "kubernetes",
            "competency_name": "Kubernetes",
        },
        evidence_by_id={},
        weak_area={
            "competency_key": "kubernetes",
            "message": "No confirmed Kubernetes evidence",
        },
    )

    assert answer["format"] == "honest_gap_response"
    assert "без overclaim" in answer["situation"]
    assert "No confirmed Kubernetes evidence" in answer["task"]
    assert "Не заявлять опыт, который не подтверждён фактами" in answer["tradeoffs"][0]
    assert answer["fact_status"] == "inferred_needs_review"


def test_gap_answer_is_profession_neutral() -> None:
    service = InterviewAnswerSynthesisService()

    answer = service._build_gap_answer(
        question={
            "competency_name": "Adobe Photoshop",
        },
        weak_area={
            "message": "No confirmed Adobe Photoshop evidence",
        },
    )

    combined = " ".join(
        [
            *answer["tradeoffs"],
            *answer["talking_points"],
            answer["action"],
        ]
    ).lower()

    assert "backend" not in combined
    assert "automation" not in combined
    assert "spike" not in combined
    assert "pairing" not in combined
    assert "production task" not in combined
    assert "подтверждённым опытом" in combined


def test_fallback_action_does_not_invent_backend_ownership_claim() -> None:
    service = InterviewAnswerSynthesisService()

    action = service._fallback_action(
        evidence={},
        competency="FastAPI backend development",
    )

    lowered = action.lower()

    assert "спроектировал" not in lowered
    assert "разработал" not in lowered
    assert "можно описать" in lowered
    assert "подтвержд" in lowered


def test_interview_answer_synthesis_attaches_answers_to_questions() -> None:
    service = InterviewAnswerSynthesisService()

    questions = service.attach_suggested_answers(
        questions=[
            {
                "question_id": "q-python",
                "category": "technical",
                "prompt": "Tell me about Python",
                "competency_key": "python",
                "competency_name": "Python",
                "recommended_evidence_ids": ["ev-python"],
            }
        ],
        evidence_snippets=[
            {
                "id": "ev-python",
                "title": "Built Python service",
                "snippet_text": "Built Python and FastAPI backend service.",
                "skills": ["Python", "FastAPI"],
                "fact_status": "confirmed",
                "star_summary": {},
            }
        ],
    )

    assert questions[0]["suggested_answer"]["source_evidence_id"] == "ev-python"
    assert "Python" in questions[0]["suggested_answer"]["tech_stack"]


def test_answer_synthesis_does_not_build_star_from_ownership_review_noise() -> None:
    service = InterviewAnswerSynthesisService()

    answer = service.build_answer(
        question={
            "category": "technical",
            "competency_name": "Adobe Photoshop",
            "recommended_evidence_ids": ["ev-1"],
        },
        evidence_by_id={
            "ev-1": {
                "id": "ev-1",
                "title": "Участвовала в ребрендинге продуктовой линейки",
                "fact_status": "confirmed",
                "skills": ["leadership"],
                "star_summary": {
                    "situation": "В проекте ребрендинга",
                    "task": "Подготовить макеты",
                    "action": (
                        "Участвовала в ребрендинге продуктовой линейки "
                        "Extracted as a normalized contribution signal; "
                        "candidate ownership must be reviewed before strong use in documents"
                    ),
                    "result": "Обновлена визуальная система продукта",
                },
            }
        },
    )

    assert answer["grounding_status"] == "grounded"
    assert "Extracted as a normalized contribution signal" not in answer["action"]
    assert "candidate ownership must be reviewed" not in answer["action"].lower()
    assert answer["tech_stack"] == []


def test_answer_synthesis_builds_grounded_star_from_confirmed_clean_evidence() -> None:
    service = InterviewAnswerSynthesisService()

    answer = service.build_answer(
        question={
            "category": "technical",
            "competency_name": "Adobe Photoshop",
            "recommended_evidence_ids": ["ev-1"],
        },
        evidence_by_id={
            "ev-1": {
                "id": "ev-1",
                "title": "Подготовка макетов",
                "fact_status": "confirmed",
                "skills": ["Adobe Photoshop", "leadership"],
                "star_summary": {
                    "situation": "Нужно было подготовить макеты для печати",
                    "task": "Адаптировать материалы под требования типографии",
                    "action": "Подготовила макеты в Adobe Photoshop",
                    "result": "Материалы были переданы в печать без доработок",
                },
            }
        },
    )

    assert answer["grounding_status"] == "grounded"
    assert answer["action"] == "Подготовила макеты в Adobe Photoshop"
    assert answer["tech_stack"] == ["Adobe Photoshop"]


def test_answer_synthesis_uses_partial_evidence_when_fact_exists_but_star_incomplete() -> None:
    service = InterviewAnswerSynthesisService()

    answer = service.build_answer(
        question={
            "category": "technical",
            "competency_name": "Adobe Photoshop",
            "recommended_evidence_ids": ["ev-1"],
        },
        evidence_by_id={
            "ev-1": {
                "id": "ev-1",
                "title": "Сократила сроки подготовки макетов на 30%",
                "fact_status": "confirmed",
                "star_summary": {
                    "situation": "",
                    "task": "",
                    "action": "",
                    "result": "",
                },
            }
        },
    )

    assert answer["grounding_status"] == "partial_evidence"
    assert "Есть релевантный факт" in answer["situation"]
    assert "Дособрать задачу" in answer["task"]
    assert "Недостаточно подтверждённых данных" not in answer["draft_text"]
