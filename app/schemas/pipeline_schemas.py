# app\schemas\pipeline_schemas.py

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.readiness_models import ReadinessScore
from app.domain.recommendation_models import RecommendationTask


class PipelineStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PROFILE_LOADING = "profile_loading"
    VACANCY_ANALYSIS = "vacancy_analysis"
    ACHIEVEMENT_RETRIEVAL = "achievement_retrieval"
    COVERAGE_MAPPING = "coverage_mapping"
    DOCUMENT_GENERATION = "document_generation"
    DOCUMENT_EVALUATION = "document_evaluation"
    READINESS_SCORING = "readiness_scoring"
    REVIEW_GATE = "review_gate"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventSeverityEnum(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PipelineEventTypeEnum(str, Enum):
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    EVALUATION_FAILED = "evaluation_failed"
    REVIEW_REQUIRED = "review_required"
    REVIEW_COMPLETED = "review_completed"
    RECOMMENDATION_GENERATED = "recommendation_generated"


class PipelineExecutionCreate(BaseModel):
    user_id: UUID
    document_id: UUID
    vacancy_id: UUID
    profile_id: Optional[UUID] = None
    pipeline_version: str = Field(default="v1.0", description="Version of the pipeline")
    calibration_version: Optional[str] = None


class PipelineExecutionResponse(BaseModel):
    id: UUID
    user_id: UUID
    vacancy_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    status: PipelineStatusEnum
    review_required: bool = False
    review_completed: bool = False
    pipeline_version: Optional[str] = None
    calibration_version: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    execution_duration_ms: Optional[int] = None
    evaluation_duration_ms: Optional[int] = None
    mutation_duration_ms: Optional[int] = None
    resume_document_id: Optional[UUID] = None
    evaluation_snapshot_id: Optional[UUID] = None
    review_id: Optional[UUID] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    artifacts_json: dict[str, Any] = Field(default_factory=dict)
    metrics_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PipelineExecutionStepCreate(BaseModel):
    execution_id: UUID
    step_name: str
    input_artifact_ids: list[str] = Field(default_factory=list)


class PipelineExecutionStepResponse(BaseModel):
    id: UUID
    execution_id: UUID
    step_name: str
    status: StepStatusEnum
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PipelineEventCreate(BaseModel):
    execution_id: UUID
    event_type: PipelineEventTypeEnum
    step_id: Optional[UUID] = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    severity: EventSeverityEnum = EventSeverityEnum.INFO


class PipelineEventResponse(BaseModel):
    id: UUID
    execution_id: UUID
    event_type: PipelineEventTypeEnum
    step_id: Optional[UUID] = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    severity: EventSeverityEnum
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecutionEventTimelineItem(BaseModel):
    event_type: str
    created_at: datetime
    payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class PipelineExecutionSummaryResponse(BaseModel):
    execution: PipelineExecutionResponse
    steps: list[PipelineExecutionStepResponse] = Field(default_factory=list)
    events: list[PipelineEventResponse] = Field(default_factory=list)
    total_duration_ms: Optional[int] = None
    failed_steps: list[PipelineExecutionStepResponse] = Field(default_factory=list)
    completed_steps: list[PipelineExecutionStepResponse] = Field(default_factory=list)


class PipelineExecutionListResponse(BaseModel):
    items: list[PipelineExecutionResponse] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class StepUpdateRequest(BaseModel):
    status: Optional[StepStatusEnum] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    output_artifact_ids: Optional[list[str]] = None
    error_message: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None


class ExecutionUpdateRequest(BaseModel):
    status: Optional[PipelineStatusEnum] = None
    review_required: Optional[bool] = None
    review_completed: Optional[bool] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    execution_duration_ms: Optional[int] = None
    evaluation_duration_ms: Optional[int] = None
    mutation_duration_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    artifacts_json: Optional[dict[str, Any]] = None
    metrics_json: Optional[dict[str, Any]] = None
    resume_document_id: Optional[UUID] = None
    evaluation_snapshot_id: Optional[UUID] = None
    review_id: Optional[UUID] = None


class CareerCopilotRunResponse(BaseModel):
    """Complete career copilot run response with progress, artifacts, readiness, tasks, and review status."""

    # Pipeline execution data
    execution: PipelineExecutionResponse
    steps: list[PipelineExecutionStepResponse] = Field(default_factory=list)
    events: list[PipelineEventResponse] = Field(default_factory=list)
    total_duration_ms: Optional[int] = None
    failed_steps: list[PipelineExecutionStepResponse] = Field(default_factory=list)
    completed_steps: list[PipelineExecutionStepResponse] = Field(default_factory=list)

    # Progress information
    progress: dict[str, Any] = Field(default_factory=dict)

    # Artifacts (from pipeline execution)
    artifacts: dict[str, Any] = Field(default_factory=dict)

    # Readiness score
    readiness: ReadinessScore | None = None

    # Recommendation tasks
    tasks: list[RecommendationTask] = Field(default_factory=list)

    # Review status
    review_status: str = "draft"

    model_config = ConfigDict(from_attributes=True)
