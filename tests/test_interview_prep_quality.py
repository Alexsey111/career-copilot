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
    assert any(item["key"] == "prompt_engineering" for item in competency_map["evidence_competencies"])

    evidence_question = next(
        item
        for item in questions
        if item["category"] == "evidence_probe"
        and item["competency_key"] == "prompt_engineering"
    )
    assert evidence_question["source_type"] == "extracted_evidence"
    assert evidence_question["fact_status"] == "user_provided"
    assert evidence_question["recommended_evidence_ids"] == ["ev-1"]
    assert "prompt engineering" in evidence_question["prompt"]


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
    assert "No confirmed domain-specific evidence" not in messages
