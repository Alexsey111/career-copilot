"""add evidence snippets and usages tables

Revision ID: h8c9d0e1f2a3
Revises: 8b9c0d1e2f3a
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h8c9d0e1f2a3"
down_revision = "8b9c0d1e2f3a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_snippets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("snippet_text", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("skills_json", sa.JSON(), nullable=False),
        sa.Column("evidence_strength", sa.String(length=20), nullable=False),
        sa.Column("fact_status", sa.String(length=20), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("used_in_documents_count", sa.Integer(), nullable=False),
        sa.Column("used_in_interviews_count", sa.Integer(), nullable=False),
        sa.Column("star_summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "fingerprint", name="uq_evidence_snippets_user_fingerprint"),
    )
    op.create_index("ix_evidence_snippets_user_id", "evidence_snippets", ["user_id"])
    op.create_index("ix_evidence_snippets_user_source", "evidence_snippets", ["user_id", "source_type"])

    op.create_table(
        "evidence_usages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_snippet_id", sa.Uuid(), nullable=False),
        sa.Column("usage_type", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_snippet_id"], ["evidence_snippets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_usages_user_id", "evidence_usages", ["user_id"])
    op.create_index("ix_evidence_usages_evidence_snippet_id", "evidence_usages", ["evidence_snippet_id"])
    op.create_index("ix_evidence_usages_snippet_usage", "evidence_usages", ["evidence_snippet_id", "usage_type"])


def downgrade() -> None:
    op.drop_index("ix_evidence_usages_snippet_usage", table_name="evidence_usages")
    op.drop_index("ix_evidence_usages_evidence_snippet_id", table_name="evidence_usages")
    op.drop_index("ix_evidence_usages_user_id", table_name="evidence_usages")
    op.drop_table("evidence_usages")

    op.drop_index("ix_evidence_snippets_user_source", table_name="evidence_snippets")
    op.drop_index("ix_evidence_snippets_user_id", table_name="evidence_snippets")
    op.drop_table("evidence_snippets")
