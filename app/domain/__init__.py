"""Domain package for business logic."""

from app.domain.execution_metrics import (
    MetricTimeWindow,
    PipelineHealthStatus,
    DurationMetrics,
    SuccessRateMetrics,
    ReviewMetrics,
    FailureMetrics,
    RecommendationMetrics,
    ResumeSuccessMetrics,
    ExecutionMetrics,
    TrendMetrics,
)
from app.domain.execution_events import ExecutionEventType
from app.domain.execution_event_payloads import (
    ExecutionCancelledPayload,
    ExecutionCompletedPayload,
    ExecutionFailedPayload,
    ExecutionStartedPayload,
    EvaluationCompletedPayload,
    EvaluationFailedPayload,
    RecommendationAppliedPayload,
    StepCompletedPayload,
    StepFailedPayload,
    StepStartedPayload,
    ReviewCompletedPayload,
    ReviewRequiredPayload,
    serialize_execution_event_payload,
)
from app.domain.pipeline_execution_status import PipelineExecutionStatus
from app.domain.document_diff import (
    DocumentDiffResult,
    SectionDiff,
)
from app.domain.evidence import (
    EvidenceFactStatus,
    EvidenceSnippet,
    EvidenceSourceType,
    EvidenceStrengthLevel,
    EvidenceUsage,
    STAREvidenceSummary,
    build_evidence_fingerprint,
    build_evidence_text,
    build_star_summary,
    extract_skill_tags,
)
from app.domain.readiness_evaluation import (
    ReadinessLevel,
    ComponentScore,
    ReadinessEvaluation,
)

__all__ = [
    # Execution Metrics
    "MetricTimeWindow",
    "PipelineHealthStatus",
    "DurationMetrics",
    "SuccessRateMetrics",
    "ReviewMetrics",
    "FailureMetrics",
    "RecommendationMetrics",
    "ResumeSuccessMetrics",
    "ExecutionMetrics",
    "TrendMetrics",
    "ExecutionEventType",
    "ExecutionStartedPayload",
    "EvaluationCompletedPayload",
    "RecommendationAppliedPayload",
    "ReviewRequiredPayload",
    "ReviewCompletedPayload",
    "ExecutionCompletedPayload",
    "ExecutionCancelledPayload",
    "ExecutionFailedPayload",
    "EvaluationFailedPayload",
    "StepStartedPayload",
    "StepCompletedPayload",
    "StepFailedPayload",
    "serialize_execution_event_payload",
    "PipelineExecutionStatus",
    "SectionDiff",
    "DocumentDiffResult",
    # Evidence
    "EvidenceFactStatus",
    "EvidenceSnippet",
    "EvidenceSourceType",
    "EvidenceStrengthLevel",
    "EvidenceUsage",
    "STAREvidenceSummary",
    "build_evidence_fingerprint",
    "build_evidence_text",
    "build_star_summary",
    "extract_skill_tags",
    # Readiness Evaluation
    "ReadinessLevel",
    "ComponentScore",
    "ReadinessEvaluation",
]
