from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    CandidateProfile,
    DocumentVersion,
    EvidenceSnippet,
    FileExtraction,
    InterviewAnswerAttempt,
    InterviewSession,
    User,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def fresh_user(db_session: AsyncSession) -> User:
    user = User(
        email=f"enc-{uuid.uuid4().hex[:8]}@local.test",
        password_hash="x",
        auth_provider="email",
        oauth_access_token="oauth-secret-token-12345",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def test_document_version_encrypted_at_rest(
    db_session: AsyncSession, fresh_user: User
) -> None:
    payload = {"name": "Иван Иванов", "email": "ivan@example.com", "sections": [{"body": "secret"}]}
    doc = DocumentVersion(
        user_id=fresh_user.id,
        document_kind="resume",
        content_json=payload,
        rendered_text="Contact: ivan@example.com +7 999 123-45-67",
    )
    db_session.add(doc)
    await db_session.flush()

    # ORM read returns plaintext-equivalent values.
    await db_session.refresh(doc)
    assert doc.content_json == payload
    assert "ivan@example.com" in doc.rendered_text

    # Raw SQL bypasses the TypeDecorator and returns the encrypted token.
    raw_content = await db_session.scalar(
        text("SELECT content_json FROM document_versions WHERE id = :id"),
        {"id": doc.id},
    )
    raw_rendered = await db_session.scalar(
        text("SELECT rendered_text FROM document_versions WHERE id = :id"),
        {"id": doc.id},
    )
    assert isinstance(raw_content, str)
    assert "ivan@example.com" not in raw_content
    assert "Иван" not in raw_content
    assert isinstance(raw_rendered, str)
    assert "ivan@example.com" not in raw_rendered


async def test_file_extraction_and_evidence_encrypted_at_rest(
    db_session: AsyncSession, fresh_user: User
) -> None:
    extraction = FileExtraction(
        parser_name="test-parser",
        extracted_text="Резюме: Иван Иванович, email ivan@example.com",
    )
    db_session.add(extraction)

    snippet = EvidenceSnippet(
        user_id=fresh_user.id,
        fingerprint=f"fp-{uuid.uuid4().hex}",
        title="Achievement",
        snippet_text="Увеличил выручку на 40%, ivan@example.com",
    )
    db_session.add(snippet)
    await db_session.flush()

    await db_session.refresh(extraction)
    await db_session.refresh(snippet)
    assert "ivan@example.com" in extraction.extracted_text
    assert "Увеличил выручку" in snippet.snippet_text

    raw_extracted = await db_session.scalar(
        text("SELECT extracted_text FROM file_extractions WHERE id = :id"),
        {"id": extraction.id},
    )
    raw_snippet = await db_session.scalar(
        text("SELECT snippet_text FROM evidence_snippets WHERE id = :id"),
        {"id": snippet.id},
    )
    assert "ivan@example.com" not in raw_extracted
    assert "Увеличил выручку" not in raw_snippet


async def test_candidate_profile_and_interview_encrypted_at_rest(
    db_session: AsyncSession, fresh_user: User
) -> None:
    profile = CandidateProfile(
        user_id=fresh_user.id,
        full_name="Иван Иванов",
        location="г. Москва",
        summary="Опытный разработчик, ivan@example.com",
    )
    db_session.add(profile)

    session = InterviewSession(
        user_id=fresh_user.id,
        answers_json=[{"question_id": "q1", "answer": "мой ответ ivan@example.com"}],
        feedback_json={"q1": {"score": 8, "note": "хорошо"}},
    )
    db_session.add(session)
    await db_session.flush()

    attempt = InterviewAnswerAttempt(
        session_id=session.id,
        question_id="q1",
        answer_text="Подробный ответ кандидата ivan@example.com",
    )
    db_session.add(attempt)
    await db_session.flush()

    await db_session.refresh(profile)
    await db_session.refresh(session)
    await db_session.refresh(attempt)
    assert profile.full_name == "Иван Иванов"
    assert session.answers_json[0]["answer"] == "мой ответ ivan@example.com"
    assert session.feedback_json["q1"]["score"] == 8
    assert "ivan@example.com" in attempt.answer_text

    raw_full_name = await db_session.scalar(
        text("SELECT full_name FROM candidate_profiles WHERE id = :id"),
        {"id": profile.id},
    )
    raw_summary = await db_session.scalar(
        text("SELECT summary FROM candidate_profiles WHERE id = :id"),
        {"id": profile.id},
    )
    raw_answers = await db_session.scalar(
        text("SELECT answers_json FROM interview_sessions WHERE id = :id"),
        {"id": session.id},
    )
    raw_answer_text = await db_session.scalar(
        text("SELECT answer_text FROM interview_answer_attempts WHERE id = :id"),
        {"id": attempt.id},
    )
    assert raw_full_name != "Иван Иванов"
    assert "ivan@example.com" not in raw_summary
    assert "ivan@example.com" not in raw_answers
    assert "ivan@example.com" not in raw_answer_text


async def test_oauth_access_token_encrypted_at_rest(
    db_session: AsyncSession, fresh_user: User
) -> None:
    # fresh_user.oauth_access_token was set in the fixture; reload from DB.
    reloaded = (
        await db_session.execute(select(User).where(User.id == fresh_user.id))
    ).scalar_one()
    assert reloaded.oauth_access_token == "oauth-secret-token-12345"

    raw_token = await db_session.scalar(
        text("SELECT oauth_access_token FROM users WHERE id = :id"),
        {"id": fresh_user.id},
    )
    assert raw_token != "oauth-secret-token-12345"
    assert "oauth-secret" not in raw_token