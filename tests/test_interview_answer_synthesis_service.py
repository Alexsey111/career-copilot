from __future__ import annotations

from app.services.interview_answer_synthesis_service import (
    InterviewAnswerSynthesisService,
)


def test_interview_answer_synthesis_builds_star_answer_from_repository_evidence() -> None:
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
        "fact_status": "confirmed",
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
    assert answer["situation"] == "Нужно было собрать AI Career Copilot workflow."
    assert "FastAPI backend" in answer["action"]
    assert "FastAPI" in answer["tech_stack"]
    assert "OpenAI" in answer["tech_stack"]
    assert any("persistence boundaries" in item for item in answer["tradeoffs"])
    assert "Situation:" in answer["draft_text"]
    assert answer["source_evidence_id"] == "ev-career-copilot"


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
    assert "Не заявлять production experience" in answer["tradeoffs"][0]
    assert answer["fact_status"] == "inferred_needs_review"


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
