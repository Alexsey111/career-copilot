"""add subscription.ai_provider

Revision ID: z1c2d3e4f5g6
Revises: y0b1c2d3e4f5
Create Date: 2026-07-24 00:00:00.000000

#37 DeepSeek — per-user LLM-провайдер. Новая колонка ``subscriptions.ai_provider``
(NULL = использовать ``settings.ai_provider``). Не backfill, не index —
выбор провайдера — единичная запись per-user, lookup идёт по user_id
(unique constraint уже есть).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "z1c2d3e4f5g6"
down_revision = "y0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("ai_provider", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "ai_provider")
