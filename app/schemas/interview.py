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
    question_id: str = Field(min_length=1, max_length=100)
    question_index: int = Field(ge=0)
    answer_text: str = Field(default="", max_length=5000)


class InterviewAnswersUpdateRequest(BaseModel):
    answers: list[InterviewAnswerItem]


class InterviewSessionRead(BaseModel):
    id: UUID
    vacancy_id: UUID | None
    session_type: str
    status: str
    mode: str = "preparation"
    current_question_index: int | None = None
    completed_at: datetime | None = None
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
    mode: str = "preparation"
    current_question_index: int | None = None
    completed_at: datetime | None = None
    question_count: int
    answered_count: int
    unanswered_count: int
    warning_count: int
    readiness_score: int | None
    competency_readiness: list[dict[str, Any]] = Field(default_factory=list)
    weak_competencies: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class InterviewAnswerEvaluateRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=100)
    answer_text: str


class InterviewAnswerEvaluateResponse(BaseModel):
    score: float
    feedback: list[str]


class InterviewCompetencyDetailResponse(BaseModel):
    competency: dict[str, Any]
    questions: list[dict[str, Any]]
    answers: list[dict[str, Any]]
    feedback_items: list[dict[str, Any]]
    attempts: list[dict[str, Any]] = Field(default_factory=list)


class InterviewQuestionAttemptCreateRequest(BaseModel):
    answer_text: str = Field(min_length=1, max_length=5000)
    update_session_answer: bool = True


class InterviewAnswerImproveRequest(BaseModel):
    question_text: str
    answer_text: str


class InterviewAnswerImproveResponse(BaseModel):
    improved_answer: str
    explanation: str


class InterviewAnswerAdvisoryRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=100)
    answer_text: str = Field(min_length=1, max_length=5000)
    competency_key: str | None = None


class InterviewAnswerAdvisoryResponse(BaseModel):
    strong_parts: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    star_improvements: list[str] = Field(default_factory=list)
    specificity_gaps: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    suggested_revision: str = ""
    confirmation_needed: list[str] = Field(default_factory=list)


class InterviewMockCurrentResponse(BaseModel):
    question_index: int
    question: dict[str, Any]
    progress: dict[str, Any]


class InterviewMockAnswerRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=100)
    answer_text: str = Field(min_length=1, max_length=5000)
    include_advisory: bool = False


class InterviewMockAnswerResponse(BaseModel):
    session: InterviewSessionRead
    evaluation: dict[str, Any]
    advisory: dict[str, Any] | None = None
    completed: bool
    next_question: dict[str, Any] | None = None
    progress: dict[str, Any]


class InterviewMockSummaryResponse(BaseModel):
    session: InterviewSessionRead
    progress: dict[str, Any]
    readiness_score: int | None = None
    competency_readiness: list[dict[str, Any]] = Field(default_factory=list)
    weak_competencies: list[dict[str, Any]] = Field(default_factory=list)
    attempt_count: int = 0


class InterviewAttemptProgressResponse(BaseModel):
    attempts: list[dict]
    progress: dict
    last_diff: dict | None = None
    coaching: dict | None = None
