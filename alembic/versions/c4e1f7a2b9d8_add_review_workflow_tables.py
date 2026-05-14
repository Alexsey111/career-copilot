"""add review workflow tables

Revision ID: c4e1f7a2b9d8
Revises: a9d7c6b5e4f3
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4e1f7a2b9d8"
down_revision: Union[str, Sequence[str], None] = "a9d7c6b5e4f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("pipeline_execution_id", sa.Uuid(as_uuid=True), sa.ForeignKey("pipeline_executions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="review_required"),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_duration_ms", sa.Integer(), nullable=True),
        sa.Column("final_status", sa.String(length=50), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_review_sessions_document_status", "review_sessions", ["document_id", "status"], unique=False)
    op.create_index("idx_review_sessions_user_status", "review_sessions", ["user_id", "status"], unique=False)
    op.create_index("idx_review_sessions_created_at", "review_sessions", ["created_at"], unique=False)

    op.create_table(
        "review_actions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("review_session_id", sa.Uuid(as_uuid=True), sa.ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("action_payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_review_actions_session_created", "review_actions", ["review_session_id", "created_at"], unique=False)
    op.create_index("idx_review_actions_action_type", "review_actions", ["action_type"], unique=False)

    op.create_table(
        "review_outcomes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("review_session_id", sa.Uuid(as_uuid=True), sa.ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome_status", sa.String(length=50), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("outcome_payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_review_outcomes_session_created", "review_outcomes", ["review_session_id", "created_at"], unique=False)
    op.create_index("idx_review_outcomes_status_approved", "review_outcomes", ["outcome_status", "approved"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_review_outcomes_status_approved", table_name="review_outcomes")
    op.drop_index("idx_review_outcomes_session_created", table_name="review_outcomes")
    op.drop_table("review_outcomes")

    op.drop_index("idx_review_actions_action_type", table_name="review_actions")
    op.drop_index("idx_review_actions_session_created", table_name="review_actions")
    op.drop_table("review_actions")

    op.drop_index("idx_review_sessions_created_at", table_name="review_sessions")
    op.drop_index("idx_review_sessions_user_status", table_name="review_sessions")
    op.drop_index("idx_review_sessions_document_status", table_name="review_sessions")
    op.drop_table("review_sessions")
