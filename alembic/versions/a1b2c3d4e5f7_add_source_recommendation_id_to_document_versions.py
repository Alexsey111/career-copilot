"""Add source_recommendation_id to document_versions

Revision ID: a1b2c3d4e5f7
Revises: f0a1b2c3d4e5
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: str | None = 'f0a1b2c3d4e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add source_recommendation_id foreign key to document_versions."""
    op.add_column(
        'document_versions',
        sa.Column(
            'source_recommendation_id',
            sa.Uuid(as_uuid=True),
            nullable=True,
        )
    )
    op.create_foreign_key(
        'fk_document_versions_source_recommendation',
        'document_versions',
        'recommendations',
        ['source_recommendation_id'],
        ['id'],
        ondelete='SET NULL'
    )
    # Add index for faster lookups
    op.create_index(
        'ix_document_versions_source_recommendation',
        'document_versions',
        ['source_recommendation_id']
    )


def downgrade() -> None:
    """Remove source_recommendation_id from document_versions."""
    op.drop_index(
        'ix_document_versions_source_recommendation',
        table_name='document_versions'
    )
    op.drop_constraint(
        'fk_document_versions_source_recommendation',
        'document_versions',
        type_='foreignkey'
    )
    op.drop_column('document_versions', 'source_recommendation_id')
