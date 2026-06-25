from __future__ import annotations

from types import SimpleNamespace

from app.services.cover_letter_generation_service import CoverLetterGenerationService
from app.services.document_quality_service import DocumentQualityService
from app.services.document_review_summary_service import DocumentReviewSummaryService
from app.services.interview_question_service import InterviewQuestionService
from app.services.interview_readiness_service import InterviewReadinessService
from app.services.resume_generation_service import ResumeGenerationService


class _FakeReadinessGateService:
    def evaluate_document_readiness(self, document):
        return SimpleNamespace(
            ready=True,
            blockers=[],
            warnings=[],
            score=0.9,
        )


def test_e2e_generalization_legal_case_keeps_facts_and_review_boundaries() -> None:
    resume_service = ResumeGenerationService()
    cover_service = CoverLetterGenerationService()
    question_service = InterviewQuestionService()
    readiness_service = InterviewReadinessService()
    review_service = DocumentReviewSummaryService(
        readiness_gate_service=_FakeReadinessGateService(),
        quality_service=DocumentQualityService(),
    )

    vacancy = SimpleNamespace(
        title="Главный специалист-юрист",
        company="Администрация Города Барнаула",
        location="Барнаул",
        description_raw=(
            "Знание профильного законодательства. "
            "Нормотворческая деятельность. "
            "Официально-деловой стиль. "
            "Ведение переговоров."
        ),
    )
    analysis = SimpleNamespace(
        must_have_json=[
            {"text": "знание профильного законодательства"},
            {"text": "нормотворческая деятельность"},
            {"text": "официально-деловой стиль"},
            {"text": "юриспруденция"},
        ],
        nice_to_have_json=[],
        strengths_json=[
            {"keyword": "договорное право", "scope": "must_have"},
            {"keyword": "документооборот", "scope": "must_have"},
        ],
        gaps_json=[
            {"keyword": "коммуникация", "scope": "behavioral"},
        ],
        keywords_json=[
            "договорное право",
            "документооборот",
            "нормотворческая деятельность",
        ],
        match_score=80,
    )

    profile = SimpleNamespace(
        full_name="Екатерина Волкова",
        headline="Юрист",
        location="",
        target_roles_json=["Юрист"],
        summary="Гражданское право, Договорное право, Legal Research, Документооборот, Арбитраж",
        experiences=[
            SimpleNamespace(
                company="Юридическая компания Право+",
                role="Юрист",
                start_date=None,
                end_date=None,
                description_raw=(
                    "Подготовка договоров\n"
                    "Судебное сопровождение\n"
                    "Консультирование клиентов\n"
                    "Претензионная работа"
                ),
            )
        ],
        achievements=[
            SimpleNamespace(
                id="ach-1",
                title="Подготовила более 250 договоров",
                situation=None,
                task=None,
                action="Подготовка договоров",
                result="Подготовила более 250 договоров",
                metric_text="250 договоров",
                evidence_note="Из резюме",
                fact_status="confirmed",
                skills_json=["Договорное право", "Документооборот"],
            ),
            SimpleNamespace(
                id="ach-2",
                title="Разработала шаблоны документов для отдела",
                situation=None,
                task=None,
                action="Разработка шаблонов документов",
                result=None,
                metric_text=None,
                evidence_note="Из резюме",
                fact_status="confirmed",
                skills_json=["Документооборот"],
            ),
        ],
    )

    matched_keywords, missing_keywords = resume_service._extract_match_keywords_from_analysis(
        strengths_json=analysis.strengths_json,
        gaps_json=analysis.gaps_json,
    )
    assert matched_keywords == ["договорное право", "документооборот"]
    assert missing_keywords == ["коммуникация"]

    experience_items = resume_service._build_experience_items(profile)
    raw_skills = resume_service._extract_skills_from_profile_or_raw_text(
        profile_summary=profile.summary,
        raw_text="",
    )
    selected_skills = resume_service._select_resume_skills(
        raw_skills=raw_skills,
        matched_keywords=matched_keywords,
    )
    confirmed_achievements = resume_service._get_confirmed_achievements(
        profile.achievements
    )
    selected_achievements = resume_service._select_relevant_achievements(
        confirmed_achievements,
        matched_keywords,
    )

    assert "Договорное право" in selected_skills
    assert "Документооборот" in selected_skills
    assert selected_achievements
    assert all(item["fact_status"] == "confirmed" for item in selected_achievements)

    resume_document = SimpleNamespace(
        document_kind="resume",
        content_json={
            "sections": {
                "matched_keywords": matched_keywords,
                "missing_keywords": missing_keywords,
                "skills": selected_skills,
                "experience": experience_items,
                "selected_achievements": selected_achievements,
                "claims_needing_confirmation": [],
                "warnings": [],
            },
            "meta": {
                "source": "e2e_test",
            },
        },
        rendered_text=(
            "Екатерина Волкова\nЮрист\n"
            "Договорное право\nДокументооборот\n"
            "Подготовила более 250 договоров"
        ),
    )

    resume_summary = review_service.build_summary(resume_document)

    assert resume_summary["provenance"]["requires_human_review"] is True
    assert resume_summary["quality"]["document_kind"] == "resume"
    assert resume_summary["selected_achievements"]

    relevance = cover_service._build_relevance_paragraph(
        matched_keywords=matched_keywords,
        selected_achievements=selected_achievements,
        selected_evidence=[],
        missing_keywords=missing_keywords,
        profile_skills=selected_skills,
        vacancy_title=vacancy.title,
        candidate_experiences=profile.experiences,
    )
    closing = cover_service._build_closing(
        vacancy_title=vacancy.title,
        company=vacancy.company,
        candidate_experiences=profile.experiences,
        selected_skills=selected_skills,
        matched_keywords=matched_keywords,
    )

    assert "организации закупок" not in closing.lower()
    assert "контроле поставок" not in closing.lower()
    assert "250" in relevance or "договор" in relevance.lower()

    cover_document = SimpleNamespace(
        document_kind="cover_letter",
        review_status="draft",
        is_active=False,
        content_json={
            "sections": {
                "matched_keywords": matched_keywords,
                "missing_keywords": missing_keywords,
                "selected_achievements": selected_achievements,
                "relevance_paragraph": relevance,
                "closing": closing,
            },
            "meta": {
                "source": "e2e_test",
            },
        },
        rendered_text=f"{relevance}\n\n{closing}",
    )

    cover_summary = review_service.build_summary(cover_document)

    assert cover_summary["provenance"]["requires_human_review"] is True
    assert cover_summary["quality"]["document_kind"] == "cover_letter"

    evidence_snippets = [
        {
            "id": "ach-1",
            "title": "Подготовила более 250 договоров",
            "snippet_text": "Подготовила более 250 договоров",
            "source_type": "manual",
            "skills": ["Договорное право", "Документооборот"],
            "fact_status": "confirmed",
            "evidence_strength": "strong",
            "star_summary": {
                "action": "Подготовка договоров",
                "result": "250 договоров",
            },
        },
        {
            "id": "ach-2",
            "title": "Разработала шаблоны документов для отдела",
            "snippet_text": "Разработала шаблоны документов для отдела",
            "source_type": "manual",
            "skills": ["Документооборот"],
            "fact_status": "confirmed",
            "evidence_strength": "medium",
            "star_summary": {
                "action": "Разработка шаблонов документов",
            },
        },
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

    assert "юриспруденция" in domain_labels
    assert "юриспруденция" not in required_labels

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

    prompts = [item["prompt"] for item in questions]

    assert questions
    assert not any("Расскажите про юриспруденцию" in prompt for prompt in prompts)
    assert not any(
        question.get("competency_name") == "юриспруденция"
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