import pytest
from uuid import UUID

from app.services.interview_prep_service import InterviewPrepService


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
