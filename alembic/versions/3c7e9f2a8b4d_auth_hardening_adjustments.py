"""auth hardening adjustments

Revision ID: 3c7e9f2a8b4d
Revises: a1b2c3d4e5f6
Create Date: 2026-04-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c7e9f2a8b4d"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "auth_provider",
        existing_type=sa.String(length=50),
        nullable=False,
        existing_server_default="email",
    )

    op.alter_column(
        "refresh_sessions",
        "token_hash",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "refresh_sessions",
        "token_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
        nullable=False,
    )

    op.alter_column(
        "users",
        "auth_provider",
        existing_type=sa.String(length=50),
        nullable=True,
        existing_server_default="email",
    )
