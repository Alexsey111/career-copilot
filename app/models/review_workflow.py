"""Persistent review workflow models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewSessionRecord(Base):
    """Persistent human review session."""

    __tablename__ = "review_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    session_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    pipeline_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pipeline_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="review_required", index=True)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    final_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    actions: Mapped[list["ReviewActionRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ReviewActionRecord.created_at.asc()",
    )
    outcomes: Mapped[list["ReviewOutcomeRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ReviewOutcomeRecord.created_at.asc()",
    )

    __table_args__ = (
        Index("idx_review_sessions_document_status", "document_id", "status"),
        Index("idx_review_sessions_user_status", "user_id", "status"),
        Index("idx_review_sessions_created_at", "created_at"),
    )


class ReviewActionRecord(Base):
    """Persistent action taken during a review session."""

    __tablename__ = "review_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    review_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("review_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    action_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    session: Mapped["ReviewSessionRecord"] = relationship(back_populates="actions")

    __table_args__ = (
        Index("idx_review_actions_session_created", "review_session_id", "created_at"),
    )


class ReviewOutcomeRecord(Base):
    """Persistent final outcome of a review session."""

    __tablename__ = "review_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    review_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("review_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outcome_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    outcome_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    session: Mapped["ReviewSessionRecord"] = relationship(back_populates="outcomes")

    __table_args__ = (
        Index("idx_review_outcomes_session_created", "review_session_id", "created_at"),
        Index("idx_review_outcomes_status_approved", "outcome_status", "approved"),
    )
