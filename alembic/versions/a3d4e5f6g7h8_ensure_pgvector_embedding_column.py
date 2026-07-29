"""ensure pgvector extension and convert vacancy.embedding text->vector

Revision ID: a3d4e5f6g7h8
Revises: z1c2d3e4f5g6
Create Date: 2026-07-29 00:00:01.000000

Контекст: миграция l2c3d4e5f6g7 проверяла ``_has_vector_extension`` и, если
extension не установлен, создавала колонку ``vacancies.embedding`` как ``Text``
(строка "[1,2,...]") вместо ``vector(384)``. На образе ``pgvector/pgvector:pg16``
extension доступен, но ``CREATE EXTENSION`` никто не вызывал → semantic-search
падал с ``type "vector" does not exist`` (500), а модель SQLAlchemy
``Vector(384)`` расходилась со схемой.

Эта миграция:
1. ``CREATE EXTENSION IF NOT EXISTS vector`` — идемпотентно.
2. Если колонка ``embedding`` имеет тип ``text`` — конвертирует в ``vector(384)``
   через ``USING embedding::vector(384)`` (pgvector поддерживает text→vector cast,
   данные "[1,2,...]" сохраняются; NULL остаётся NULL).
3. Создаёт ivfflat-индекс, если его нет.

Идемпотентна: на БД, где extension уже был и колонка уже vector, ничего не ломает.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "a3d4e5f6g7h8"
down_revision = "z1c2d3e4f5g6"
branch_labels = None
depends_on = None


def _embedding_data_type(bind) -> str | None:
    try:
        result = bind.execute(
            sa.text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'vacancies' AND column_name = 'embedding'"
            )
        )
        return result.scalar()
    except Exception:
        return None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Extension (доступен на pgvector/pgvector:pg16).
    bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # 2. Конвертация text -> vector(384), если колонка создалась как Text.
    col_type = _embedding_data_type(bind)
    if col_type == "text":
        bind.execute(
            sa.text(
                "ALTER TABLE vacancies ALTER COLUMN embedding "
                "TYPE vector(384) USING embedding::vector(384)"
            )
        )

    # 3. Индекс (ivfflat). IF NOT NOT EXISTS — pgvector поддерживает.
    bind.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_vacancies_embedding ON vacancies "
            "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    try:
        bind.execute(sa.text("DROP INDEX IF EXISTS ix_vacancies_embedding"))
    except Exception:
        pass
    # Обратно в text не конвертируем намеренно — потеря cosine-индекса при
    # откате достаточна; данные в vector остаются читаемыми как text-представление.