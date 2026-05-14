"""merge impact and review heads

Revision ID: d1e2f3a4b5c6
Revises: 9c2d1e4f6a7b, c4e1f7a2b9d8
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = ("9c2d1e4f6a7b", "c4e1f7a2b9d8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
