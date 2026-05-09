"""
Pydantic-контракты для JSON-полей в БД.

Валидация после LLM, перед сохранением.
Не нормализуем таблицы — только структурируем JSON.
"""

from __future__ import annotations

from uuid import UUID

from typing import Any, Literal

from pydantic import Field, field_validator

from app.schemas.base import StrictBaseModel
from app.schemas.common_types import (
    ContentSource,
    DocumentKind,
    FactStatus,
    RequirementScope,
)

ReviewStatus = Literal[
    "draft",
    "review_required",
    "reviewed",
    "approved",
    "archived",
]

ReviewerAction = Literal[
    "accept_all",
    "reject_all",
    "accept_selected",
    "reject_selected",
    "edit_and_accept",
]

ReviewSeverity = Literal[
    "info",
    "warning",
    "critical",
]

InterviewQuestionSource = Literal[
    "vacancy",
    "vacancy_analysis.must_have",
    "vacancy_analysis.gaps",
    "vacancy_analysis.strengths",
    "candidate_achievements",
]

DraftMode = Literal[
    "deterministic_v1_review_ready",
    "ai_enhanced_v1",
]

# ---------------------------------------------------------------------------
# VacancyAnalysis JSON fields
# ---------------------------------------------------------------------------

class RequirementItem(StrictBaseModel):
    """Один требование из must_have / nice_to_have."""
    text: str
    scope: RequirementScope = "must_have"
    keyword: str | None = None
    weight: int | None = None


class GapItem(StrictBaseModel):
    """Один gap из gaps_json."""
    keyword: str
    scope: RequirementScope = "must_have"
    reason: str | None = None
    requirement_text: str | None = None
    weight: int | None = None


class StrengthItem(StrictBaseModel):
    """Один strength из strengths_json."""
    keyword: str
    scope: RequirementScope = "must_have"
    evidence: str | None = None
    requirement_text: str | None = None
    weight: int | None = None


class VacancyAnalysisSchema(StrictBaseModel):
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

class ContentMeta(StrictBaseModel):
    """Мета-информация о происхождении контента.
    
    source: откуда пришёл контент
        - "extracted" — извлечён из исходных файлов пользователя
        - "ai_generated" — сгенерирован LLM
        - "user_edited" — отредактирован пользователем
        - "hybrid" — смесь вышеперечисленного
    
    based_on_achievements: UUID-ы достижений, на основе которых
        сгенерирован этот контент (для explainability)
    
    based_on_analysis_id: UUID анализа вакансии, использованного
        для генерации (redundant с DocumentVersion.analysis_id,
        но полезен для self-contained JSON)
    
    confidence: уверенность в фактах (0-1)
        - 1.0 = подтверждено пользователем или извлечено
        - 0.5-0.9 = сгенерировано на основе подтверждённых данных
        - 0.1-0.4 = предположение / gap mitigation
    
    generation_prompt_version: какая версия промпта использовалась
    
    generation_trace: трассировка генерации для debugging и evaluation
        selected_achievement_ids, matched_keywords, missing_keywords,
        builder_version, renderer_version, prompt_version
    
    ai_metadata: аудит-трейл для AI enhancement
        model, prompt_version, temperature, safety_checks_passed
    """
    source: ContentSource = "ai_generated"
    based_on_achievements: list[UUID] = Field(default_factory=list)
    based_on_analysis_id: UUID | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    generation_prompt_version: str | None = None
    generated_at: str | None = None  # ISO timestamp
    warnings: list["WarningItem"] = Field(default_factory=list)

    # Generation trace for explainability
    generation_trace: dict[str, Any] = Field(default_factory=dict)

    # AI audit trail for enhancement operations
    ai_metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateInfo(StrictBaseModel):
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    target_roles: list[str] = Field(default_factory=list)


class TargetVacancy(StrictBaseModel):
    vacancy_id: UUID
    title: str
    company: str | None = None
    location: str | None = None


class AchievementItem(StrictBaseModel):
    id: UUID | None = None
    title: str
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metric_text: str | None = None
    fact_status: FactStatus = "confirmed"
    reason: str = "profile_core"


class WarningItem(StrictBaseModel):
    code: str
    message: str
    severity: str = "warning"


class ClaimItem(StrictBaseModel):
    type: str
    text: str
    fact_status: FactStatus
    source: str | None = None
    resolved_at: str | None = None  # ISO timestamp when resolved
    resolution_note: str | None = None  # Why accepted/rejected


class ResolvedClaimItem(StrictBaseModel):
    """Claim after review resolution."""
    claim_text: str
    original_status: FactStatus
    final_status: FactStatus  # "confirmed" or "rejected"
    resolved_at: str
    resolved_by: str | None = None
    resolution_reason: str | None = None
    edited_text: str | None = None


class WarningItem(StrictBaseModel):
    code: str
    message: str
    severity: ReviewSeverity = "warning"
    section: str | None = None
    claim_text: str | None = None


class ExperienceItem(StrictBaseModel):
    company: str
    role: str
    period: str
    description_raw: str | None = None


class BaseResumeSections(StrictBaseModel):
    """Общий набор секций для resume-подобных документов."""
    fit_summary: dict[str, Any] = Field(default_factory=dict)
    summary_bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    selected_achievements: list[AchievementItem] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    matched_requirements: list[dict] = Field(default_factory=list)
    gap_requirements: list[dict] = Field(default_factory=list)
    claims_needing_confirmation: list[ClaimItem] = Field(default_factory=list)
    resolved_claims: list[ResolvedClaimItem] = Field(default_factory=list)
    selection_rationale: list[dict] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)


class DocumentSections(BaseResumeSections):
    pass


class DocumentContentSchema(StrictBaseModel):
    """Контракт для DocumentVersion.content_json."""
    document_kind: DocumentKind = "resume"
    draft_mode: DraftMode = "deterministic_v1_review_ready"
    candidate: CandidateInfo = Field(default_factory=CandidateInfo)
    target_vacancy: TargetVacancy | None = None
    sections: DocumentSections = Field(default_factory=DocumentSections)
    meta: ContentMeta = Field(default_factory=ContentMeta)


# ---------------------------------------------------------------------------
# Type-specific document schemas (discriminated by document_kind)
# ---------------------------------------------------------------------------

class ResumeSections(BaseResumeSections):
    """Sections для resume."""
    pass


class CoverLetterSections(StrictBaseModel):
    """Sections для cover_letter."""
    opening: str = ""
    relevance_paragraph: str = ""
    closing: str = ""
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    matched_requirements: list[dict] = Field(default_factory=list)
    gap_requirements: list[dict] = Field(default_factory=list)
    selected_achievements: list[AchievementItem] = Field(default_factory=list)
    claims_needing_confirmation: list[ClaimItem] = Field(default_factory=list)
    resolved_claims: list[ResolvedClaimItem] = Field(default_factory=list)
    warnings: list[WarningItem] = Field(default_factory=list)


class ResumeContent(StrictBaseModel):
    """Строгая схема для resume content_json."""
    document_kind: DocumentKind = "resume"
    draft_mode: DraftMode = "deterministic_v1_review_ready"
    candidate: CandidateInfo = Field(default_factory=CandidateInfo)
    target_vacancy: TargetVacancy | None = None
    sections: ResumeSections = Field(default_factory=ResumeSections)
    meta: ContentMeta = Field(default_factory=ContentMeta)


class CoverLetterContent(StrictBaseModel):
    """Строгая схема для cover_letter content_json."""
    document_kind: DocumentKind = "cover_letter"
    draft_mode: DraftMode = "deterministic_v1_review_ready"
    candidate: CandidateInfo = Field(default_factory=CandidateInfo)
    target_vacancy: TargetVacancy | None = None
    sections: CoverLetterSections = Field(default_factory=CoverLetterSections)
    meta: ContentMeta = Field(default_factory=ContentMeta)


# ---------------------------------------------------------------------------
# InterviewSession JSON fields
# ---------------------------------------------------------------------------

class InterviewQuestion(StrictBaseModel):
    """Один вопрос из question_set_json."""
    # Legacy поля (опциональные для обратной совместимости)
    question_id: str | None = None
    question_text: str | None = None
    question_type: str | None = None
    expected_keywords: list[str] = Field(default_factory=list)

    # Основные поля текущей реализации
    type: str | None = None
    source: InterviewQuestionSource | None = None
    prompt: str | None = None
    answer_format: str | None = None
    rubric: list[str] = Field(default_factory=list)
    requirement_text: str | None = None
    keyword: str | None = None
    scope: RequirementScope | None = None
    achievement_title: str | None = None
    fact_status: FactStatus | None = None


class InterviewAnswer(StrictBaseModel):
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


class InterviewScore(StrictBaseModel):
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


class InterviewSessionSchema(StrictBaseModel):
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

class AttemptFeedbackSchema(StrictBaseModel):
    """Контракт для InterviewAnswerAttempt.feedback_json."""
    feedback: list[str] = Field(default_factory=list)
    coaching: dict[str, str] | None = None
    improved_answer: str | None = None
