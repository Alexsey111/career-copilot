"""add source file lifecycle and content hash

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "i9d0e1f2a3b4"
down_revision = "h8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_files", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "source_files",
        sa.Column("lifecycle_status", sa.String(length=30), nullable=False, server_default="active"),
    )
    op.add_column("source_files", sa.Column("lineage_group_id", sa.Uuid(), nullable=True))
    op.add_column("source_files", sa.Column("superseded_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_source_files_superseded_by_id_source_files",
        "source_files",
        "source_files",
        ["superseded_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_source_files_content_sha256", "source_files", ["content_sha256"], unique=False)
    op.create_index("ix_source_files_lifecycle_status", "source_files", ["lifecycle_status"], unique=False)
    op.create_index("ix_source_files_lineage_group_id", "source_files", ["lineage_group_id"], unique=False)
    op.create_index("ix_source_files_superseded_by_id", "source_files", ["superseded_by_id"], unique=False)
    op.create_index(
        "ix_source_files_user_kind_hash",
        "source_files",
        ["user_id", "file_kind", "content_sha256"],
        unique=False,
    )
    op.alter_column("source_files", "lifecycle_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_source_files_user_kind_hash", table_name="source_files")
    op.drop_index("ix_source_files_superseded_by_id", table_name="source_files")
    op.drop_index("ix_source_files_lineage_group_id", table_name="source_files")
    op.drop_index("ix_source_files_lifecycle_status", table_name="source_files")
    op.drop_index("ix_source_files_content_sha256", table_name="source_files")
    op.drop_constraint("fk_source_files_superseded_by_id_source_files", "source_files", type_="foreignkey")
    op.drop_column("source_files", "superseded_by_id")
    op.drop_column("source_files", "lineage_group_id")
    op.drop_column("source_files", "lifecycle_status")
    op.drop_column("source_files", "content_sha256")
