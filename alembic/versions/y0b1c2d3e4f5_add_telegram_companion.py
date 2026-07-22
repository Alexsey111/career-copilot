"""add telegram companion (user columns + dispatch log)

Revision ID: y0b1c2d3e4f5
Revises: w9n0o1p2q3r4
Create Date: 2026-07-22 00:00:00.000000

Этап 5 — Telegram companion (ТЗ §3.6). Companion, not replacement: alerts,
reminders, quick resume checks, job summaries, interview prep prompts via
Telegram Bot API (httpx).

- ``users``: + ``telegram_chat_id`` (plain String(64), indexed — pseudonymous
  lookup key для webhook chat_id → user, как ``oauth_provider_id``; НЕ ПДн по
  ФЗ-152, не шифруется), ``telegram_username``, ``telegram_linked_at``,
  ``telegram_dispatch_enabled`` (per-user opt-in для proactive push).
- ``telegram_dispatch_log`` — дедуп proactive уведомлений
  (``UniqueConstraint(user_id, dispatch_key)``; ``dispatch_key`` =
  ``{reminder_type}:{application_id}:{YYYY-MM-DD}``).

Без backfill — новые колонки/таблица. Образец: n4e5f6g7h8i9 / w9n0o1p2q3r4.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "y0b1c2d3e4f5"
down_revision = "w9n0o1p2q3r4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users: telegram companion columns ---
    op.add_column("users", sa.Column("telegram_chat_id", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("telegram_username", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("telegram_linked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("telegram_dispatch_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_users_telegram_chat_id", "users", ["telegram_chat_id"])

    # --- telegram_dispatch_log: dedup table ---
    op.create_table(
        "telegram_dispatch_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_key", sa.String(length=200), nullable=False),
        sa.Column("dispatch_type", sa.String(length=50), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "dispatch_key", name="uq_telegram_dispatch_log_user_key"),
    )
    op.create_index("ix_telegram_dispatch_log_user_id", "telegram_dispatch_log", ["user_id"])
    op.create_index("ix_telegram_dispatch_log_dispatch_type", "telegram_dispatch_log", ["dispatch_type"])


def downgrade() -> None:
    op.drop_index("ix_telegram_dispatch_log_dispatch_type", table_name="telegram_dispatch_log")
    op.drop_index("ix_telegram_dispatch_log_user_id", table_name="telegram_dispatch_log")
    op.drop_table("telegram_dispatch_log")

    op.drop_index("ix_users_telegram_chat_id", table_name="users")
    op.drop_column("users", "telegram_dispatch_enabled")
    op.drop_column("users", "telegram_linked_at")
    op.drop_column("users", "telegram_username")
    op.drop_column("users", "telegram_chat_id")