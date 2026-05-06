# backend\alembic\script.py.mako

"""add analysis_id to document_versions

Revision ID: 5505206e59d7
Revises: 1458eac2b109
Create Date: 2026-05-06 13:00:27.895809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '5505206e59d7'
down_revision: Union[str, Sequence[str], None] = '1458eac2b109'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_versions",
        sa.Column(
            "analysis_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("vacancy_analyses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_document_versions_analysis_id",
        "document_versions",
        ["analysis_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_versions_analysis_id", table_name="document_versions")
    op.drop_column("document_versions", "analysis_id")