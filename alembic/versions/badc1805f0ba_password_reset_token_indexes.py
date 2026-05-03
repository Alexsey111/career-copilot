# backend\alembic\script.py.mako

"""password_reset_token_indexes

Revision ID: badc1805f0ba
Revises: b2c3d4e5f6a7
Create Date: 2026-05-03 18:07:18.232059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'badc1805f0ba'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_password_reset_tokens_expires_at",
        "password_reset_tokens",
        ["expires_at"],
    )

    op.create_index(
        "ix_password_reset_tokens_used_at",
        "password_reset_tokens",
        ["used_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_used_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")