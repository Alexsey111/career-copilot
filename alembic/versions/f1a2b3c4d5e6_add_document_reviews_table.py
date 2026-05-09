"""add document_reviews table

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2025-05-09 20:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_action", sa.String(length=50), nullable=False),
        sa.Column("final_status", sa.String(length=50), nullable=False, default="reviewed"),
        sa.Column("accepted_claims_json", sa.JSON(), nullable=False, default=list),
        sa.Column("rejected_claims_json", sa.JSON(), nullable=False, default=list),
        sa.Column("edited_sections_json", sa.JSON(), nullable=False, default=list),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("eval_report_json", sa.JSON(), nullable=True),
        sa.Column("has_critical_failures", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_document_reviews_document_id", "document_reviews", ["document_id"])
    op.create_index("ix_document_reviews_user_id", "document_reviews", ["user_id"])
    op.create_index("ix_document_reviews_document_user", "document_reviews", ["document_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_document_reviews_document_user", table_name="document_reviews")
    op.drop_index("ix_document_reviews_user_id", table_name="document_reviews")
    op.drop_index("ix_document_reviews_document_id", table_name="document_reviews")
    op.drop_table("document_reviews")
