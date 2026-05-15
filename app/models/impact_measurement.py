# app/models/impact_measurement.py

"""ImpactMeasurement model — persistent storage for recommendation impact measurements."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import Float, JSON, String, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImpactRecommendationType(str, Enum):
    """Explicit recommendation type stored in impact measurements."""

    ADD_METRIC = "add_metric"
    ADD_EVIDENCE = "add_evidence"
    IMPROVE_DESCRIPTION = "improve_description"
    ADD_QUANTIFIABLE_RESULT = "add_quantifiable_result"
    ADD_TIMEFRAME = "add_timeframe"
    ADD_CONTEXT = "add_context"
    SPLIT_ACHIEVEMENT = "split_achievement"
    MERGE_ACHIEVEMENTS = "merge_achievements"
    ADD_SKILL_KEYWORD = "add_skill_keyword"
    REMOVE_REDUNDANT = "remove_redundant"
    IMPROVE_COVERAGE = "improve_coverage"
    UNKNOWN = "unknown"


class ImpactMeasurement(Base):
    """
    Persistent record of recommendation impact measurement.

    Позволяет:
    - Analytics по рекомендациям
    - Ranking качества рекомендаций
    - Adaptive recommendations
    - User progress history
    """

    __tablename__ = "impact_measurements"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    recommendation_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )
    recommendation_type: Mapped[ImpactRecommendationType] = mapped_column(
        SQLEnum(
            ImpactRecommendationType,
            name="impact_recommendation_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ImpactRecommendationType.UNKNOWN,
        index=True,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )

    before_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )

    after_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Delta scores
    delta_overall: Mapped[float] = mapped_column(Float, nullable=False)
    delta_components: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_impact_measurements_recommendation_id", "recommendation_id"),
        Index("ix_impact_measurements_recommendation_type", "recommendation_type"),
        Index("ix_impact_measurements_document_id", "document_id"),
        Index("ix_impact_measurements_created_at", "created_at"),
    )
