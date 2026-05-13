# backend\alembic\script.py.mako

"""merge pipeline and evaluation heads

Revision ID: 167331481783
Revises: 31848a56031c, b1c2d3e4f5g6
Create Date: 2026-05-13 14:45:53.149295

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '167331481783'
down_revision: Union[str, Sequence[str], None] = ('31848a56031c', 'b1c2d3e4f5g6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass