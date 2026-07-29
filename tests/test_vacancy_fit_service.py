from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.vacancy_fit_service import VacancyFitService


class _VacancyRepo:
    def __init__(self, vacancy) -> None:
        self.vacancy = vacancy

    async def get_by_id(self, session, vacancy_id, *, user_id):  # noqa: D401
        return self.vacancy


class _AnalysisRepo:
    def __init__(self, analysis) -> None:
        self.analysis = analysis

    async def get_latest_for_vacancy(self, session, vacancy_id, *, user_id):  # noqa: D401
        return self.analysis


class _ProfileRepo:
    def __init__(self, profile) -> None:
        self.profile = profile

    async def get_with_related_by_user_id(self, session, user_id):  # noqa: D401
        return self.profile


class _EvidenceRepo:
    def __init__(self, snippets) -> None:
        self.snippets = snippets

    async def list_by_user_id(self, session, *, user_id, source_types=None):  # noqa: D401
        return self.snippets


@pytest.mark.asyncio
async def test_vacancy_fit_service_classifies_gap_severity_and_evidence_coverage() -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        title="Senior Backend Engineer",
        company="Acme",
        location="Remote",
        description_raw=(
            "Must have: Kubernetes, Leadership, Stakeholder communication.\n"
            "Python is also required."
        ),
    )
    analysis = SimpleNamespace(
        id=uuid4(),
        analysis_version="deterministic_v1",
        must_have_json=[
            {"text": "Kubernetes"},
            {"text": "Leadership"},
            {"text": "Stakeholder communication"},
            {"text": "Python"},
        ],
        nice_to_have_json=[
            {"text": "Redis"},
        ],
        keywords_json=["Kubernetes", "Leadership", "Stakeholder communication", "Python", "Redis"],
    )
    profile = SimpleNamespace(
        full_name="Test Candidate",
        headline="Backend Engineer",
        location="Remote",
        summary="I build backend systems and work closely with stakeholders.",
        target_roles_json=["Backend Engineer"],
        experiences=[
            SimpleNamespace(
                company="Acme",
                role="Backend Engineer",
                description_raw="Led delivery, coordinated stakeholders, and shipped Python services.",
            )
        ],
        achievements=[
            SimpleNamespace(
                title="Stakeholder communication",
                situation="The team needed a clearer release plan.",
                task="Keep stakeholders aligned.",
                action="I ran weekly updates and collected feedback.",
                result="The release stayed on track.",
                metric_text=None,
                evidence_note=None,
            )
        ],
    )
    snippets = [
        SimpleNamespace(
            id=uuid4(),
            title="Stakeholder communication",
            snippet_text="Weekly updates for product and support stakeholders.",
            source_type="achievement",
            skills_json=["Stakeholder communication", "communication"],
            evidence_strength="strong",
            fact_status="confirmed",
            usage_count=0,
            used_in_documents_count=0,
            used_in_interviews_count=0,
            star_summary_json={
                "situation": "Release coordination needed alignment",
                "task": "Keep stakeholders informed",
                "action": "Sent weekly updates",
                "result": "Release stayed on track",
            },
        ),
        SimpleNamespace(
            id=uuid4(),
            title="Leadership",
            snippet_text="Led backend delivery and mentored one engineer.",
            source_type="achievement",
            skills_json=["Leadership", "mentoring"],
            evidence_strength="medium",
            fact_status="confirmed",
            usage_count=0,
            used_in_documents_count=0,
            used_in_interviews_count=0,
            star_summary_json={
                "situation": "Team needed delivery support",
                "task": "Coordinate work",
                "action": "Led the backend stream",
                "result": "Milestones were met",
            },
        ),
    ]

    service = VacancyFitService(
        vacancy_repository=_VacancyRepo(vacancy),
        vacancy_analysis_repository=_AnalysisRepo(analysis),
        candidate_profile_repository=_ProfileRepo(profile),
        evidence_snippet_repository=_EvidenceRepo(snippets),
    )

    fit = await service.build_vacancy_fit(
        None,
        vacancy_id=vacancy.id,
        user_id=uuid4(),
    )

    assert fit["vacancy_id"] == vacancy.id
    assert fit["analysis_id"] == analysis.id
    assert fit["gap_severity"] == "critical"
    assert fit["readiness_recommendation"] == "Large evidence gaps"
    assert 0 <= fit["overall_fit_score"] <= 100

    required = fit["evidence_coverage"]["required"]
    assert any("kubernetes" in str(item).casefold() for item in required)
    assert any("leadership" in str(item).casefold() for item in required)
    assert any("stakeholder" in str(item).casefold() for item in required)

    strong = fit["evidence_coverage"]["strong"]
    medium = fit["evidence_coverage"]["medium"]
    missing = fit["evidence_coverage"]["missing"]

    assert any("stakeholder" in str(item["requirement"]).casefold() for item in strong)
    assert any("leadership" in str(item["requirement"]).casefold() for item in medium)
    assert any("kubernetes" in str(item["requirement"]).casefold() for item in missing)

    stakeholder_item = next(
        item for item in strong if "stakeholder" in str(item["requirement"]).casefold()
    )
    assert stakeholder_item["supporting_evidence"]
    assert stakeholder_item["supporting_evidence"][0]["fact_status"] == "confirmed"
    assert stakeholder_item["supporting_evidence"][0]["evidence_strength"] == "strong"


@pytest.mark.asyncio
async def test_vacancy_fit_service_uses_user_provided_project_evidence() -> None:
    vacancy = SimpleNamespace(
        id=uuid4(),
        title="AI Automation Engineer",
        company="Acme",
        location="Remote",
        description_raw="Must have: computer vision, AI workflow and no-code automation.",
    )
    analysis = SimpleNamespace(
        id=uuid4(),
        analysis_version="deterministic_v1",
        must_have_json=[
            {"text": "Computer vision"},
            {"text": "AI Workflow"},
            {"text": "No-code"},
        ],
        nice_to_have_json=[],
        keywords_json=["Computer vision", "AI Workflow", "No-code"],
    )
    profile = SimpleNamespace(
        full_name="Test Candidate",
        headline="AI Engineer",
        location="Remote",
        summary="AI automation and computer vision projects.",
        target_roles_json=["AI Automation Engineer"],
        experiences=[],
        achievements=[],
    )
    snippets = [
        SimpleNamespace(
            id=uuid4(),
            title="Автоматизированный ИИ-контроль качества",
            snippet_text=(
                "Computer vision automation workflow for quality control "
                "from images and video."
            ),
            source_type="resume_structured",
            skills_json=["AI", "computer vision", "automation"],
            evidence_strength="strong",
            fact_status="user_provided",
            usage_count=0,
            used_in_documents_count=0,
            used_in_interviews_count=0,
            star_summary_json={
                "category": "automation",
                "source": "structured_resume_extraction_v2",
            },
        )
    ]

    service = VacancyFitService(
        vacancy_repository=_VacancyRepo(vacancy),
        vacancy_analysis_repository=_AnalysisRepo(analysis),
        candidate_profile_repository=_ProfileRepo(profile),
        evidence_snippet_repository=_EvidenceRepo(snippets),
    )

    fit = await service.build_vacancy_fit(
        None,
        vacancy_id=vacancy.id,
        user_id=uuid4(),
    )

    covered = fit["evidence_coverage"]["strong"] + fit["evidence_coverage"]["medium"]
    assert any("computer" in str(item["requirement"]).casefold() for item in covered)
    assert any("workflow" in str(item["requirement"]).casefold() for item in covered)
    assert any("no-code" in str(item["requirement"]).casefold() for item in covered)
    assert fit["evidence_fit"] > 0
    assert fit["requirements"][0]["supporting_evidence"][0]["fact_status"] == "user_provided"


def test_collapse_requirements_by_text_dedupes_display_duplicates() -> None:
    """Один must_have пункт, из которого _extract_keywords достаёт N ключевых
    слов, порождает N записей с одинаковым ``requirement``-текстом. Для display
    это дубль (ноут #91: «Опыт работы с Cursor» → 3 AI-ключа → 3 строки в
    missing). _collapse_requirements_by_text сворачивает их в один пункт с
    лучшим coverage_level и объединённым evidence (дедуб по evidence_id)."""
    service = VacancyFitService(
        vacancy_repository=_VacancyRepo(None),
        vacancy_analysis_repository=_AnalysisRepo(None),
        candidate_profile_repository=_ProfileRepo(None),
        evidence_snippet_repository=_EvidenceRepo([]),
    )
    eid_a, eid_b = uuid4(), uuid4()
    items = [
        {
            "requirement": "Опыт работы с Cursor",
            "scope": "must_have",
            "severity": "minor",
            "coverage_level": "missing",
            "reason": "r1",
            "evidence_ids": [],
            "supporting_evidence": [],
        },
        {
            "requirement": "Опыт работы с Cursor",
            "scope": "must_have",
            "severity": "moderate",
            "coverage_level": "strong",
            "reason": "r2",
            "evidence_ids": [str(eid_a)],
            "supporting_evidence": [{"evidence_id": str(eid_a), "fact_status": "confirmed"}],
        },
        {
            "requirement": "Опыт работы с Cursor",
            "scope": "must_have",
            "severity": "moderate",
            "coverage_level": "medium",
            "reason": "r3",
            "evidence_ids": [str(eid_b)],
            "supporting_evidence": [{"evidence_id": str(eid_b), "fact_status": "user_provided"}],
        },
    ]

    collapsed = service._collapse_requirements_by_text(items)

    assert len(collapsed) == 1
    only = collapsed[0]
    assert only["requirement"] == "Опыт работы с Cursor"
    # Лучший coverage (strong) побеждает — берём его поля.
    assert only["coverage_level"] == "strong"
    assert only["reason"] == "r2"
    # Evidence объединён из всех вариантов, дедуп по evidence_id.
    assert set(only["evidence_ids"]) == {str(eid_a), str(eid_b)}
    assert len(only["supporting_evidence"]) == 2


@pytest.mark.asyncio
async def test_build_vacancy_fit_collapses_multi_keyword_requirement() -> None:
    """End-to-end: одна фраза требования, из которой _extract_keywords достаёт
    3 ключа → 3 сигнала с одним ``requirement``. До фикса в
    ``evidence_coverage.missing`` лежало 3 одинаковые строки; после — одна.
    Общая эвристика (через monkeypatch каталога), БЕЗ хардкода профессии."""
    vacancy = SimpleNamespace(
        id=uuid4(),
        title="Any Role",
        company="Acme",
        location="Remote",
        description_raw="Must have: опыт работы с Cursor.",
    )
    analysis = SimpleNamespace(
        id=uuid4(),
        analysis_version="deterministic_v1",
        must_have_json=[{"text": "Опыт работы с Cursor"}],
        nice_to_have_json=[],
        keywords_json=["Опыт работы с Cursor"],
    )
    profile = SimpleNamespace(
        full_name="Test Candidate",
        headline="Any",
        location="Remote",
        summary="",
        target_roles_json=["Any"],
        experiences=[],
        achievements=[],
    )

    service = VacancyFitService(
        vacancy_repository=_VacancyRepo(vacancy),
        vacancy_analysis_repository=_AnalysisRepo(analysis),
        candidate_profile_repository=_ProfileRepo(profile),
        evidence_snippet_repository=_EvidenceRepo([]),
    )
    # Один must_have пункт → 3 ключа каталога → 3 сигнала с одним requirement.
    service._extract_keywords = lambda label: ["Ключевой навык 1", "Ключевой навык 2", "Ключевой навык 3"]

    fit = await service.build_vacancy_fit(None, vacancy_id=vacancy.id, user_id=uuid4())

    req_texts = [str(item["requirement"]) for item in fit["requirements"]]
    assert req_texts == ["Опыт работы с Cursor"], f"expected single collapsed item, got {req_texts}"
    missing = fit["evidence_coverage"]["missing"]
    assert len(missing) == 1
    assert missing[0]["requirement"] == "Опыт работы с Cursor"
    # required-список тоже без дублей.
    assert fit["evidence_coverage"]["required"] == ["Опыт работы с Cursor"]
