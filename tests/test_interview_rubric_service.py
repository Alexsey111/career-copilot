from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status

from app.domain.case_prep import STABLE_CASE_TYPES, build_rubric
from app.domain.interview_rubric_scoring import RUBRIC_VERSION
from app.services.interview_rubric_service import InterviewRubricService


pytestmark = pytest.mark.asyncio


class _StubVacancy:
    def __init__(self, *, found: bool = True) -> None:
        self.found = found
        self.calls: list[dict] = []

    async def get_by_id(self, session, vacancy_id, *, user_id):
        self.calls.append({"vacancy_id": vacancy_id, "user_id": user_id})
        return object() if self.found else None


class _StubAttempt:
    def __init__(self, *, stored: list | None = None) -> None:
        self.last_create_kwargs: dict | None = None
        self._stored = stored or []

    async def create(self, session, **kwargs):
        self.last_create_kwargs = dict(kwargs)

        class _Attempt:
            pass

        a = _Attempt()
        a.id = uuid4()
        a.created_at = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
        return a

    async def list_by_user_vacancy_case(self, session, *, user_id, vacancy_id, case_id):
        return list(self._stored)


def _full_answer(case_type: str) -> str:
    from app.domain.interview_rubric_scoring import _RUBRIC_TOKENS

    tokens: list[str] = []
    for crit_tokens in _RUBRIC_TOKENS[case_type].values():
        tokens.extend(crit_tokens)
    return " ".join(tokens)


async def test_submit_answer_persists_and_scores() -> None:
    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(),
        attempt_repo=_StubAttempt(),
    )
    result = await service.submit_answer(
        session=None,
        user_id=uuid4(),
        vacancy_id=uuid4(),
        case_id="ipc_abc",
        case_type="system_design",
        answer_text=_full_answer("system_design"),
    )
    assert result["overall_score"] == 100.0
    assert result["grade"] == "excellent"
    assert result["requires_human_review"] is True
    assert isinstance(result["criterion_scores"], list)
    assert len(result["criterion_scores"]) == 5
    assert isinstance(result["attempt_id"], str)
    assert UUID(result["attempt_id"])
    repo = service.attempt_repo
    assert repo.last_create_kwargs is not None
    assert repo.last_create_kwargs["case_id"] == "ipc_abc"
    assert repo.last_create_kwargs["case_type"] == "system_design"
    assert repo.last_create_kwargs["overall_score"] == 100.0


async def test_submit_answer_404_foreign_vacancy_no_persist() -> None:
    attempt = _StubAttempt()
    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(found=False),
        attempt_repo=attempt,
    )
    with pytest.raises(HTTPException) as exc:
        await service.submit_answer(
            session=None,
            user_id=uuid4(),
            vacancy_id=uuid4(),
            case_id="ipc_abc",
            case_type="system_design",
            answer_text="scalab throughput",
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert attempt.last_create_kwargs is None


async def test_submit_answer_400_invalid_case_type() -> None:
    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(),
        attempt_repo=_StubAttempt(),
    )
    with pytest.raises(HTTPException) as exc:
        await service.submit_answer(
            session=None,
            user_id=uuid4(),
            vacancy_id=uuid4(),
            case_id="ipc_abc",
            case_type="bogus",
            answer_text="some answer",
        )
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_submit_answer_400_empty_answer() -> None:
    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(),
        attempt_repo=_StubAttempt(),
    )
    with pytest.raises(HTTPException) as exc:
        await service.submit_answer(
            session=None,
            user_id=uuid4(),
            vacancy_id=uuid4(),
            case_id="ipc_abc",
            case_type="system_design",
            answer_text="   ",
        )
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_list_attempts_returns_ordered_dicts() -> None:
    class _A:
        pass

    a1, a2 = _A(), _A()
    a1.id = uuid4()
    a1.case_id = "ipc_abc"
    a1.case_type = "system_design"
    a1.overall_score = 30.0
    a1.grade = "weak"
    a1.created_at = datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
    a2.id = uuid4()
    a2.case_id = "ipc_abc"
    a2.case_type = "system_design"
    a2.overall_score = 85.0
    a2.grade = "excellent"
    a2.created_at = datetime(2026, 7, 13, 11, 0, 0, tzinfo=timezone.utc)

    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(),
        attempt_repo=_StubAttempt(stored=[a1, a2]),
    )
    items = await service.list_attempts(
        session=None, user_id=uuid4(), vacancy_id=uuid4(), case_id="ipc_abc"
    )
    assert len(items) == 2
    assert items[0]["overall_score"] == 30.0
    assert items[1]["overall_score"] == 85.0
    assert all("attempt_id" in i and "created_at" in i for i in items)


async def test_list_attempts_404_foreign() -> None:
    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(found=False),
        attempt_repo=_StubAttempt(),
    )
    with pytest.raises(HTTPException) as exc:
        await service.list_attempts(
            session=None, user_id=uuid4(), vacancy_id=uuid4(), case_id="ipc_abc"
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_build_progress_empty() -> None:
    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(),
        attempt_repo=_StubAttempt(stored=[]),
    )
    progress = await service.build_progress(
        session=None, user_id=uuid4(), vacancy_id=uuid4(), case_id="ipc_abc"
    )
    assert progress["total_attempts"] == 0
    assert progress["reason"] == "no attempts yet"
    assert progress["overall"] is None
    assert progress["per_criterion"] == []


async def test_build_progress_with_attempts() -> None:
    crits = build_rubric("system_design")
    case_type = "system_design"

    class _A:
        pass

    a1, a2 = _A(), _A()
    a1.overall_score = 30.0
    a1.criterion_scores_json = [
        {"criterion": c, "score": 0, "level": "none", "reason": ""} for c in crits
    ]
    a2.overall_score = 85.0
    a2.criterion_scores_json = [
        {"criterion": c, "score": 3, "level": "high", "reason": ""} for c in crits
    ]

    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(),
        attempt_repo=_StubAttempt(stored=[a1, a2]),
    )
    progress = await service.build_progress(
        session=None, user_id=uuid4(), vacancy_id=uuid4(), case_id="ipc_abc"
    )
    assert progress["total_attempts"] == 2
    assert progress["overall"]["first"] == 30.0
    assert progress["overall"]["last"] == 85.0
    assert progress["overall"]["trend"] == "improving"
    assert len(progress["per_criterion"]) == len(crits)
    assert all(p["improvement"] == 3 for p in progress["per_criterion"])


async def test_build_progress_404_foreign() -> None:
    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(found=False),
        attempt_repo=_StubAttempt(),
    )
    with pytest.raises(HTTPException) as exc:
        await service.build_progress(
            session=None, user_id=uuid4(), vacancy_id=uuid4(), case_id="ipc_abc"
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_rubric_version_in_result_and_persist() -> None:
    attempt = _StubAttempt()
    service = InterviewRubricService(
        vacancy_repo=_StubVacancy(),
        attempt_repo=attempt,
    )
    result = await service.submit_answer(
        session=None,
        user_id=uuid4(),
        vacancy_id=uuid4(),
        case_id="ipc_abc",
        case_type="behavioral_case",
        answer_text=_full_answer("behavioral_case"),
    )
    assert result["rubric_version"] == RUBRIC_VERSION
    assert attempt.last_create_kwargs["rubric_version"] == RUBRIC_VERSION


async def test_all_case_types_accepted() -> None:
    for case_type in STABLE_CASE_TYPES:
        service = InterviewRubricService(
            vacancy_repo=_StubVacancy(),
            attempt_repo=_StubAttempt(),
        )
        result = await service.submit_answer(
            session=None,
            user_id=uuid4(),
            vacancy_id=uuid4(),
            case_id=f"ipc_{case_type}",
            case_type=case_type,
            answer_text=_full_answer(case_type),
        )
        assert result["overall_score"] == 100.0, case_type
        assert result["grade"] == "excellent", case_type