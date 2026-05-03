"""add updated_at to refresh sessions

Revision ID: 9a7b6c5d4e3f
Revises: 8f1a2b3c4d5e
Create Date: 2026-05-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a7b6c5d4e3f"
down_revision: Union[str, Sequence[str], None] = "8f1a2b3c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "refresh_sessions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("refresh_sessions", "updated_at")
