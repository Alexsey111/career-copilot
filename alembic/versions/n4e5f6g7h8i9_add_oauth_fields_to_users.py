"""add oauth fields to users table

Revision ID: n4e5f6g7h8i9
Revises: m3d4e5f6g7h8
Create Date: 2026-07-02 00:00:04.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "n4e5f6g7h8i9"
down_revision = "m3d4e5f6g7h8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("oauth_provider_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("oauth_access_token", sa.String(1000), nullable=True))
    op.create_index("ix_users_oauth_provider_id", "users", ["oauth_provider_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_oauth_provider_id", table_name="users")
    op.drop_column("users", "oauth_access_token")
    op.drop_column("users", "oauth_provider_id")
