from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class PipelineStatus(Enum):
    """Status of a career copilot pipeline execution."""
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


class PipelineEventType(Enum):
    """Типы событий pipeline."""
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    EVALUATION_FAILED = "evaluation_failed"
    REVIEW_REQUIRED = "review_required"
    RECOMMENDATION_GENERATED = "recommendation_generated"


class StepStatus(Enum):
    """Status of a pipeline execution step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventSeverity(Enum):
    """Уровень важности события."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class CareerCopilotRun:
    """Represents a single execution of the career copilot pipeline."""
    id: str
    user_id: str
    vacancy_id: str
    profile_id: str

    # Artifacts produced
    resume_document_id: Optional[str] = None
    evaluation_snapshot_id: Optional[str] = None
    review_id: Optional[str] = None
    review_session_id: Optional[str] = None

    # Execution metadata
    status: PipelineStatus = PipelineStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    pipeline_version: str = "v1.0"
    calibration_version: Optional[str] = None

    # Error handling
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Artifacts and metrics
    artifacts: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    # Additional context
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PipelineExecutionStep:
    """Represents a single step within a pipeline execution."""
    id: str
    execution_id: str
    step_name: str
    status: StepStatus = StepStatus.PENDING
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    input_artifact_ids: list[str] = field(default_factory=list)
    output_artifact_ids: list[str] = field(default_factory=list)
    
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineEvent:
    """Represents a structured event from pipeline execution."""
    id: str
    execution_id: str
    event_type: PipelineEventType
    
    step_id: Optional[str] = None
    payload: dict[str, Any] = field(default_factory=dict)
    severity: EventSeverity = EventSeverity.INFO
    
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PipelineExecutionSummary:
    """Aggregate view of a pipeline execution with steps and events."""
    execution: CareerCopilotRun
    steps: list[PipelineExecutionStep] = field(default_factory=list)
    events: list[PipelineEvent] = field(default_factory=list)
    
    @property
    def total_duration_ms(self) -> Optional[int]:
        if self.execution.started_at and self.execution.completed_at:
            return int((self.execution.completed_at - self.execution.started_at).total_seconds() * 1000)
        return None
    
    @property
    def failed_steps(self) -> list[PipelineExecutionStep]:
        return [s for s in self.steps if s.status == StepStatus.FAILED]
    
    @property
    def completed_steps(self) -> list[PipelineExecutionStep]:
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]