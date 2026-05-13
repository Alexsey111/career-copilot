# app/models/evaluation_snapshot.py

"""EvaluationSnapshot model — persistent storage for readiness evaluations."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import Float, JSON, String, DateTime, ForeignKey, Index
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, backref

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entities import DocumentVersion


class EvaluationSnapshot(Base):
    """
    Persistent snapshot of a readiness evaluation.

    Позволяет:
    - Сравнивать snapshots во времени
    - Audit scoring decisions
    - Rollback к предыдущей версии
    - Diff scoring versions
    """

    __tablename__ = "evaluation_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Scores
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    ats_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_score: Mapped[float] = mapped_column(Float, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Readiness level
    readiness_level: Mapped[str] = mapped_column(String(50), nullable=False)

    # Scoring metadata
    scoring_version: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Issues
    blockers_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    warnings_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Additional metadata
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Chain relationship for delta history
    previous_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_snapshots.id"),
        nullable=True,
        index=True,
    )

    # Relationships
    document: Mapped["DocumentVersion"] = relationship(
        back_populates="evaluation_snapshots",
        foreign_keys=[document_id],
    )

    # Self-referential relationship for snapshot chain
    previous_snapshot: Mapped["EvaluationSnapshot | None"] = relationship(
        "EvaluationSnapshot",
        remote_side="EvaluationSnapshot.id",
        foreign_keys=[previous_snapshot_id],
        backref=backref("next_snapshot", remote_side="EvaluationSnapshot.previous_snapshot_id", uselist=False),
    )

    __table_args__ = (
        Index("idx_evaluation_snapshots_document_created", "document_id", "created_at"),
        Index("idx_evaluation_snapshots_readiness_level", "readiness_level"),
        Index("idx_evaluation_snapshots_scoring_version", "scoring_version"),
        Index("idx_evaluation_snapshots_prompt_version", "prompt_version"),
        Index("idx_evaluation_snapshots_extractor_version", "extractor_version"),
        Index("idx_evaluation_snapshots_model_name", "model_name"),
    )
