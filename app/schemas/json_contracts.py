"""
Pydantic-контракты для JSON-полей в БД.

Валидация после LLM, перед сохранением.
Не нормализуем таблицы — только структурируем JSON.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# VacancyAnalysis JSON fields
# ---------------------------------------------------------------------------

class RequirementItem(BaseModel):
    """Один требование из must_have / nice_to_have."""
    text: str
    scope: str = "must_have"  # must_have | nice_to_have
    keyword: str | None = None
    weight: int | None = None


class GapItem(BaseModel):
    """Один gap из gaps_json."""
    keyword: str
    scope: str = "must_have"
    reason: str | None = None
    requirement_text: str | None = None
    weight: int | None = None


class StrengthItem(BaseModel):
    """Один strength из strengths_json."""
    keyword: str
    scope: str = "must_have"
    evidence: str | None = None
    requirement_text: str | None = None
    weight: int | None = None


class VacancyAnalysisSchema(BaseModel):
    """Контракт для VacancyAnalysis.*_json полей."""
    must_have: list[RequirementItem] = Field(default_factory=list)
    nice_to_have: list[RequirementItem] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    strengths: list[StrengthItem] = Field(default_factory=list)
    match_score: int | None = Field(default=None, ge=0, le=100)

    @field_validator("must_have", "nice_to_have", "gaps", "strengths", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> list:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        raise ValueError("must be a list")


# ---------------------------------------------------------------------------
# DocumentVersion content_json
# ---------------------------------------------------------------------------

class CandidateInfo(BaseModel):
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    target_roles: list[str] = Field(default_factory=list)


class TargetVacancy(BaseModel):
    vacancy_id: str
    title: str
    company: str | None = None
    location: str | None = None


class AchievementItem(BaseModel):
    title: str
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metric_text: str | None = None
    fact_status: str = "confirmed"
    reason: str = "profile_core"


class ExperienceItem(BaseModel):
    company: str
    role: str
    period: str
    description_raw: str | None = None


class DocumentSections(BaseModel):
    fit_summary: dict[str, Any] = Field(default_factory=dict)
    summary_bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    selected_achievements: list[AchievementItem] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    matched_requirements: list[dict] = Field(default_factory=list)
    gap_requirements: list[dict] = Field(default_factory=list)
    claims_needing_confirmation: list[dict] = Field(default_factory=list)
    selection_rationale: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentContentSchema(BaseModel):
    """Контракт для DocumentVersion.content_json."""
    document_kind: str = "resume"
    draft_mode: str = "deterministic_v1_review_ready"
    candidate: CandidateInfo = Field(default_factory=CandidateInfo)
    target_vacancy: TargetVacancy | None = None
    sections: DocumentSections = Field(default_factory=DocumentSections)


# ---------------------------------------------------------------------------
# Type-specific document schemas (discriminated by document_kind)
# ---------------------------------------------------------------------------

class ResumeSections(BaseModel):
    """Sections для resume."""
    fit_summary: dict[str, Any] = Field(default_factory=dict)
    summary_bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    selected_achievements: list[AchievementItem] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    matched_requirements: list[dict] = Field(default_factory=list)
    gap_requirements: list[dict] = Field(default_factory=list)
    claims_needing_confirmation: list[dict] = Field(default_factory=list)
    selection_rationale: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CoverLetterSections(BaseModel):
    """Sections для cover_letter."""
    opening: str = ""
    relevance_paragraph: str = ""
    closing: str = ""
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    matched_requirements: list[dict] = Field(default_factory=list)
    gap_requirements: list[dict] = Field(default_factory=list)
    selected_achievements: list[AchievementItem] = Field(default_factory=list)
    claims_needing_confirmation: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResumeContent(BaseModel):
    """Строгая схема для resume content_json."""
    document_kind: str = "resume"
    draft_mode: str = "deterministic_v1_review_ready"
    candidate: CandidateInfo = Field(default_factory=CandidateInfo)
    target_vacancy: TargetVacancy | None = None
    sections: ResumeSections = Field(default_factory=ResumeSections)


class CoverLetterContent(BaseModel):
    """Строгая схема для cover_letter content_json."""
    document_kind: str = "cover_letter"
    draft_mode: str = "deterministic_v1_review_ready"
    candidate: CandidateInfo = Field(default_factory=CandidateInfo)
    target_vacancy: TargetVacancy | None = None
    sections: CoverLetterSections = Field(default_factory=CoverLetterSections)


# ---------------------------------------------------------------------------
# InterviewSession JSON fields
# ---------------------------------------------------------------------------

class InterviewQuestion(BaseModel):
    """Один вопрос из question_set_json."""
    # Legacy поля (опциональные для обратной совместимости)
    question_id: str | None = None
    question_text: str | None = None
    question_type: str | None = None
    expected_keywords: list[str] = Field(default_factory=list)

    # Основные поля текущей реализации
    type: str | None = None
    source: str | None = None
    prompt: str | None = None
    answer_format: str | None = None
    rubric: list[str] = Field(default_factory=list)
    requirement_text: str | None = None
    keyword: str | None = None
    scope: str | None = None
    achievement_title: str | None = None
    fact_status: str | None = None


class InterviewAnswer(BaseModel):
    """Один ответ из answers_json."""
    # Legacy поля (опциональные)
    question_id: str | None = None
    answer_text: str = ""
    score: float | None = Field(default=None, ge=0, le=1)
    feedback: list[str] = Field(default_factory=list)

    # Основные поля текущей реализации
    question_index: int | None = None
    question_type: str | None = None
    answer_format: str | None = None


class InterviewScore(BaseModel):
    """Score из score_json."""
    overall: float | None = Field(default=None, ge=0, le=1)
    by_category: dict[str, float] = Field(default_factory=dict)

    # Legacy поля текущей реализации
    score_version: str | None = None
    question_count: int | None = None
    answered_count: int | None = None
    unanswered_count: int | None = None
    warning_count: int | None = None
    readiness_score: int | None = None


class InterviewSessionSchema(BaseModel):
    """Контракт для InterviewSession.*_json полей."""
    question_set: list[InterviewQuestion] = Field(default_factory=list)
    answers: list[InterviewAnswer] = Field(default_factory=list)
    feedback: dict[str, Any] = Field(default_factory=dict)
    score: InterviewScore = Field(default_factory=InterviewScore)

    @field_validator("question_set", "answers", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> list:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        raise ValueError("must be a list")


# ---------------------------------------------------------------------------
# InterviewAnswerAttempt feedback_json
# ---------------------------------------------------------------------------

class AttemptFeedbackSchema(BaseModel):
    """Контракт для InterviewAnswerAttempt.feedback_json."""
    feedback: list[str] = Field(default_factory=list)
    coaching: dict[str, str] | None = None
    improved_answer: str | None = None
