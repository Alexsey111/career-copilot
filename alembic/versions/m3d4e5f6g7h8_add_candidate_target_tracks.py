"""add candidate target tracks table

Revision ID: m3d4e5f6g7h8
Revises: l2c3d4e5f6g7
Create Date: 2026-07-02 00:00:03.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "m3d4e5f6g7h8"
down_revision = "l2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_target_tracks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("profile_id", sa.Uuid(), sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("target_roles_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("salary_expectation", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=True),
        sa.Column("location_preferences_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("work_format_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("candidate_target_tracks")
