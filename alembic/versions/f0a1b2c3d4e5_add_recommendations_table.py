"""add recommendations table

Revision ID: f0a1b2c3d4e5
Revises: e7f8a9b0c1d2
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f0a1b2c3d4e5"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


recommendation_status_enum = sa.Enum(
    "pending",
    "applied",
    "rejected",
    name="recommendation_lifecycle_status",
)


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("execution_id", sa.Uuid(as_uuid=True), sa.ForeignKey("pipeline_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Uuid(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("estimated_score_improvement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", recommendation_status_enum, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recommendations_execution_status", "recommendations", ["execution_id", "status"])
    op.create_index("ix_recommendations_document_status", "recommendations", ["document_id", "status"])
    op.create_index("ix_recommendations_created_at", "recommendations", ["created_at"])
    op.create_index("ix_recommendations_category", "recommendations", ["category"])


def downgrade() -> None:
    op.drop_index("ix_recommendations_category", table_name="recommendations")
    op.drop_index("ix_recommendations_created_at", table_name="recommendations")
    op.drop_index("ix_recommendations_document_status", table_name="recommendations")
    op.drop_index("ix_recommendations_execution_status", table_name="recommendations")
    op.drop_table("recommendations")
    recommendation_status_enum.drop(op.get_bind(), checkfirst=True)
