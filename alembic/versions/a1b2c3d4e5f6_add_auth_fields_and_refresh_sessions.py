"""add auth fields and refresh sessions

Revision ID: a1b2c3d4e5f6
Revises: 6b8d2f4a1c01
Create Date: 2026-04-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "6b8d2f4a1c01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Добавляем поля в users (с дефолтным хешем для существующих dev-записей)
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
            server_default="$argon2id$v=19$m=65536,t=3,p=4$placeholderhash$replace_me",
        ),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Создаём таблицу сессий
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_refresh_sessions_user_id"),
        "refresh_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_sessions_token_hash"),
        "refresh_sessions",
        ["token_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_sessions_expires_at"),
        "refresh_sessions",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_sessions_expires_at"), table_name="refresh_sessions")
    op.drop_index(op.f("ix_refresh_sessions_token_hash"), table_name="refresh_sessions")
    op.drop_index(op.f("ix_refresh_sessions_user_id"), table_name="refresh_sessions")
    op.drop_table("refresh_sessions")

    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_verified")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
