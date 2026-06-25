import pytest
from uuid import UUID

from app.services.interview_prep_service import InterviewPrepService
from app.services.interview_readiness_service import InterviewReadinessService


def test_build_question_summary_counts_categories_and_evidence() -> None:
    service = InterviewPrepService()

    summary = service._build_question_summary(
        [
            {
                "category": "technical",
                "recommended_evidence_ids": ["ev-1"],
                "requires_careful_answer": False,
            },
            {
                "category": "gap-risk",
                "recommended_evidence": [{"achievement_id": "ev-2"}],
                "requires_careful_answer": True,
            },
            {
                "category": "behavioral",
                "recommended_evidence_ids": [],
                "requires_careful_answer": False,
            },
        ]
    )

    assert summary == {
        "total": 3,
        "by_category": {
            "technical": 1,
            "gap-risk": 1,
            "behavioral": 1,
        },
        "careful_answer_count": 1,
        "with_evidence_count": 2,
    }


def test_build_competency_coverage_matrix_marks_confirmed_and_missing() -> None:
    service = InterviewPrepService()

    matrix = service._build_competency_coverage_matrix(
        competency_map={
            "required_skills": [
                {"key": "python", "label": "Python"},
                {"key": "kubernetes", "label": "Kubernetes"},
            ]
        },
        questions=[
            {
                "competency_key": "python",
                "recommended_evidence": [
                    {
                        "achievement_id": "ach-1",
                        "title": "Built Python backend",
                        "fact_status": "confirmed",
                    }
                ],
            }
        ],
        evidence_links=[],
        weak_areas=[
            {
                "competency_key": "kubernetes",
                "message": "No confirmed Kubernetes evidence",
            }
        ],
    )

    assert matrix == [
        {
            "competency_key": "python",
            "competency_label": "Python",
            "coverage_status": "covered",
            "evidence_status": "confirmed",
            "fact_status": "confirmed",
            "evidence_count": 1,
            "reason": "Есть подтверждённые доказательства по компетенции.",
            "suggested_next_step": "Подготовить STAR-ответ на основе найденного примера.",
        },
        {
            "competency_key": "kubernetes",
            "competency_label": "Kubernetes",
            "coverage_status": "missing",
            "evidence_status": "missing",
            "fact_status": None,
            "evidence_count": 0,
            "reason": "No confirmed Kubernetes evidence",
            "suggested_next_step": "Собрать пример из опыта: ситуация, задача, действия, результат.",
        },
    ]


def test_build_readiness_includes_structured_explanation() -> None:
    service = InterviewReadinessService()

    readiness = service.build_readiness(
        competency_map={
            "required_skills": [
                {"key": "python", "label": "Python"},
            ]
        },
        weak_areas=[
            {
                "code": "missing_confirmed_python",
                "message": "No confirmed Python evidence",
                "severity": "blocker",
                "category": "technical",
                "competency_key": "python",
                "competency_label": "Python",
            },
            {
                "code": "missing_scale_metrics",
                "message": "No scale metrics",
                "severity": "warning",
                "category": "metrics",
                "competency_key": "scale_metrics",
            },
        ],
        evidence_links=[],
    )

    explanation = readiness["explanation"]

    assert explanation == {
        "summary": "Есть критические пробелы, которые нужно закрыть перед интервью.",
        "positive_factors": [],
        "negative_factors": [
            "No confirmed Python evidence",
            "No scale metrics",
        ],
        "next_best_actions": [
            "Подтвердить опыт по компетенции: Python.",
            "Добавить измеримый результат с цифрами.",
        ],
    }


@pytest.mark.asyncio
async def test_delete_sessions_deletes_only_current_application_sessions() -> None:
    service = InterviewPrepService()

    class DummySession:
        def __init__(self) -> None:
            self.committed = False

        async def commit(self) -> None:
            self.committed = True

    class DummyRepository:
        def __init__(self) -> None:
            self.called_with_user_id = None
            self.called_with_application_id = None

        async def delete_by_application_id(self, session, *, user_id, application_id):
            self.called_with_user_id = user_id
            self.called_with_application_id = application_id
            return 3

    dummy_session = DummySession()
    dummy_repository = DummyRepository()
    service.prep_session_repository = dummy_repository

    user_id = UUID("00000000-0000-0000-0000-000000000001")
    application_id = UUID("00000000-0000-0000-0000-000000000002")

    deleted_count = await service.delete_sessions(
        dummy_session,
        user_id=user_id,
        application_id=application_id,
    )

    assert deleted_count == 3
    assert dummy_session.committed is True
    assert dummy_repository.called_with_user_id == user_id
    assert dummy_repository.called_with_application_id == application_id


@pytest.mark.asyncio
async def test_delete_sessions_by_ids_deletes_only_selected_sessions() -> None:
    service = InterviewPrepService()

    class DummySession:
        def __init__(self) -> None:
            self.committed = False

        async def commit(self) -> None:
            self.committed = True

    class DummyRepository:
        def __init__(self) -> None:
            self.called_with_user_id = None
            self.called_with_session_ids = None

        async def delete_by_ids(self, session, *, user_id, session_ids):
            self.called_with_user_id = user_id
            self.called_with_session_ids = list(session_ids)
            return 2

    dummy_session = DummySession()
    dummy_repository = DummyRepository()
    service.prep_session_repository = dummy_repository

    user_id = UUID("00000000-0000-0000-0000-000000000001")
    session_ids = [
        UUID("00000000-0000-0000-0000-000000000010"),
        UUID("00000000-0000-0000-0000-000000000011"),
    ]

    deleted_count = await service.delete_sessions_by_ids(
        dummy_session,
        user_id=user_id,
        session_ids=session_ids,
    )

    assert deleted_count == 2
    assert dummy_session.committed is True
    assert dummy_repository.called_with_user_id == user_id
    assert dummy_repository.called_with_session_ids == session_ids
