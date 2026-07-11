"""add user consents table

Revision ID: o5f6g7h8i9j0
Revises: n4e5f6g7h8i9
Create Date: 2026-07-02 00:00:05.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "o5f6g7h8i9j0"
down_revision = "n4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("consent_type", sa.String(50), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(100), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "consent_type", name="uq_user_consents_user_type"),
    )


def downgrade() -> None:
    op.drop_table("user_consents")
