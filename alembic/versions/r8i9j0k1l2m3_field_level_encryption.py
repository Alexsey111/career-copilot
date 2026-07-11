"""field-level encryption for sensitive PII columns

Revision ID: r8i9j0k1l2m3
Revises: q7h8i9j0k1l2
Create Date: 2026-07-11 00:00:08.000000

Encrypts sensitive personal data at rest (ФЗ-152 ст.19 «сохранность ПДн»)
for the core set of columns: resume/cover-letter content, extracted text,
evidence snippets, candidate PII text, interview answers/feedback, and the
OAuth access token. Each column is converted in place: an encrypted ``Text``
shadow column is added, existing rows are encrypted via the application
``encrypt_field`` helper (the DB itself has no key), the plaintext column is
dropped, and the shadow is renamed back to the original name.

Downgrade decrypts back to plaintext (data-preserving). Note: columns that
were originally ``String(255)`` are restored as ``Text`` (wider, non-lossy).
Downgrade requires reverting the ORM model code in the same change.
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

from app.security.encryption import decrypt_field, encrypt_field


revision = "r8i9j0k1l2m3"
down_revision = "q7h8i9j0k1l2"
branch_labels = None
depends_on = None


# (table, column, is_json, not_null)
_COLUMNS: list[tuple[str, str, bool, bool]] = [
    ("users", "oauth_access_token", False, False),
    ("candidate_profiles", "full_name", False, False),
    ("candidate_profiles", "location", False, False),
    ("candidate_profiles", "summary", False, False),
    ("evidence_snippets", "snippet_text", False, True),
    ("file_extractions", "extracted_text", False, True),
    ("document_versions", "content_json", True, True),
    ("document_versions", "rendered_text", False, False),
    ("interview_sessions", "answers_json", True, True),
    ("interview_sessions", "feedback_json", True, True),
    ("interview_answer_attempts", "answer_text", False, False),
]


def _encrypt_to_text(table: str, column: str, is_json: bool, not_null: bool) -> None:
    shadow = f"{column}_enc"
    op.add_column(table, sa.Column(shadow, sa.Text(), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text(f'SELECT id, "{column}" FROM {table}')).fetchall()
    for row in rows:
        raw = row[1]
        if raw is None:
            continue
        if is_json:
            raw = json.dumps(raw, ensure_ascii=False)
        bind.execute(
            sa.text(f'UPDATE {table} SET "{shadow}" = :v WHERE id = :id'),
            {"v": encrypt_field(raw), "id": row[0]},
        )
    op.drop_column(table, column)
    if not_null:
        op.alter_column(table, shadow, new_column_name=column, nullable=False)
    else:
        op.alter_column(table, shadow, new_column_name=column, nullable=True)


def _decrypt_from_text(table: str, column: str, is_json: bool) -> None:
    plain = f"{column}_plain"
    target_type = sa.JSON() if is_json else sa.Text()
    op.add_column(table, sa.Column(plain, target_type, nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text(f'SELECT id, "{column}" FROM {table}')).fetchall()
    for row in rows:
        raw = row[1]
        if raw is None:
            continue
        decrypted = decrypt_field(raw)
        if decrypted is None:
            continue
        if is_json:
            value = json.loads(decrypted)
        else:
            value = decrypted
        bind.execute(
            sa.text(f'UPDATE {table} SET "{plain}" = :v WHERE id = :id'),
            {"v": json.dumps(value, ensure_ascii=False) if is_json else value, "id": row[0]},
        )
    op.drop_column(table, column)
    op.alter_column(table, plain, new_column_name=column, nullable=True)


def upgrade() -> None:
    for table, column, is_json, not_null in _COLUMNS:
        _encrypt_to_text(table, column, is_json, not_null)


def downgrade() -> None:
    for table, column, is_json, _not_null in reversed(_COLUMNS):
        _decrypt_from_text(table, column, is_json)