# app\schemas\interview.py

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewSessionCreateRequest(BaseModel):
    vacancy_id: UUID
    session_type: str = Field(default="vacancy", min_length=1, max_length=50)


class InterviewAnswerItem(BaseModel):
    question_index: int = Field(ge=0)
    answer_text: str = Field(default="", max_length=5000)


class InterviewAnswersUpdateRequest(BaseModel):
    answers: list[InterviewAnswerItem]


class InterviewSessionRead(BaseModel):
    id: UUID
    vacancy_id: UUID | None
    session_type: str
    status: str
    question_set: list[dict[str, Any]]
    answers: list[dict[str, Any]]
    feedback: dict[str, Any]
    score: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class InterviewSessionListItem(BaseModel):
    id: UUID
    vacancy_id: UUID | None
    vacancy_title: str | None = None
    vacancy_company: str | None = None
    vacancy_location: str | None = None
    session_type: str
    status: str
    question_count: int
    answered_count: int
    unanswered_count: int
    warning_count: int
    readiness_score: int | None
    created_at: datetime
    updated_at: datetime
