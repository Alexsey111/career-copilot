# backend\app\models\entities.py

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="email",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped["CandidateProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    source_files: Mapped[list["SourceFile"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    document_versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    application_records: Mapped[list["ApplicationRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ai_runs: Mapped[list["AIRun"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_sessions: Mapped[list["RefreshSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class CandidateProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    target_roles_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    work_format_preferences_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    salary_expectation: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")
    experiences: Mapped[list["CandidateExperience"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="CandidateExperience.order_index",
    )
    achievements: Mapped[list["CandidateAchievement"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="CandidateAchievement.order_index",
    )


class CandidateExperience(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_experiences"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="experiences")
    achievements: Mapped[list["CandidateAchievement"]] = relationship(
        back_populates="experience",
        cascade="all, delete-orphan",
        order_by="CandidateAchievement.order_index",
    )


class CandidateAchievement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_achievements"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    experience_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidate_experiences.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    situation: Mapped[str | None] = mapped_column(Text, nullable=True)
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)

    metric_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidence_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    fact_status: Mapped[str] = mapped_column(String(30), nullable=False, default="needs_confirmation")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="achievements")
    experience: Mapped["CandidateExperience | None"] = relationship(back_populates="achievements")


class SourceFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_files"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="source_files")
    extractions: Mapped[list["FileExtraction"]] = relationship(
        back_populates="source_file",
        cascade="all, delete-orphan",
    )


class FileExtraction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "file_extractions"

    source_file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("source_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    source_file: Mapped["SourceFile"] = relationship(back_populates="extractions")


class Vacancy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vacancies"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    salary_from: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_to: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    description_raw: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    user: Mapped["User"] = relationship(back_populates="vacancies")
    analyses: Mapped[list["VacancyAnalysis"]] = relationship(
        back_populates="vacancy",
        cascade="all, delete-orphan",
    )
    document_versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="vacancy")
    application_records: Mapped[list["ApplicationRecord"]] = relationship(back_populates="vacancy")
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(back_populates="vacancy")


class VacancyAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vacancy_analyses"

    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vacancies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    must_have_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    nice_to_have_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    keywords_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    gaps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    strengths_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")

    vacancy: Mapped["Vacancy"] = relationship(back_populates="analyses")


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vacancies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    derived_from_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    document_kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    rendered_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="document_versions")
    vacancy: Mapped["Vacancy | None"] = relationship(back_populates="document_versions")
    parent: Mapped["DocumentVersion | None"] = relationship(remote_side="DocumentVersion.id")

    applications_as_resume: Mapped[list["ApplicationRecord"]] = relationship(
        back_populates="resume_document",
        foreign_keys="ApplicationRecord.resume_document_id",
    )
    applications_as_cover_letter: Mapped[list["ApplicationRecord"]] = relationship(
        back_populates="cover_letter_document",
        foreign_keys="ApplicationRecord.cover_letter_document_id",
    )


class ApplicationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "application_records"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "vacancy_id",
            name="uq_application_records_user_vacancy",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vacancies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cover_letter_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="application_records")
    vacancy: Mapped["Vacancy"] = relationship(back_populates="application_records")
    resume_document: Mapped["DocumentVersion | None"] = relationship(
        back_populates="applications_as_resume",
        foreign_keys=[resume_document_id],
    )
    cover_letter_document: Mapped["DocumentVersion | None"] = relationship(
        back_populates="applications_as_cover_letter",
        foreign_keys=[cover_letter_document_id],
    )


class InterviewSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "interview_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vacancy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("vacancies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    session_type: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")

    question_set_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    answers_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    feedback_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    score_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    user: Mapped["User"] = relationship(back_populates="interview_sessions")
    vacancy: Mapped["Vacancy | None"] = relationship(back_populates="interview_sessions")


class AIRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    workflow_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="started")
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="ai_runs")


class RefreshSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_sessions")


class AuthEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "auth_events"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    meta_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PasswordResetToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
