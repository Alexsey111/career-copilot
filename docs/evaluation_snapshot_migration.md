# EvaluationSnapshot Migration

## Overview

Добавлена модель `EvaluationSnapshot` для персистентного хранения оценок readiness.

## Changes

### 1. Модель: `app/models/evaluation_snapshot.py`

```python
class EvaluationSnapshot(Base):
    __tablename__ = "evaluation_snapshots"
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id"),
        nullable=False,
        index=True,
    )
    
    # Scores
    overall_score: Mapped[float]
    ats_score: Mapped[float]
    evidence_score: Mapped[float]
    coverage_score: Mapped[float]
    quality_score: Mapped[float]
    
    readiness_level: Mapped[str]
    scoring_version: Mapped[str]
    
    # JSON arrays
    blockers_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    
    created_at: Mapped[datetime]
```

### 2. Relationship в `DocumentVersion`

```python
# app/models/entities.py
class DocumentVersion(Base):
    ...
    evaluation_snapshots: Mapped[list["EvaluationSnapshot"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="EvaluationSnapshot.created_at.desc()",
    )
```

### 3. Экспорт в `app/models/__init__.py`

```python
from app.models.evaluation_snapshot import EvaluationSnapshot

__all__ = [
    ...
    "EvaluationSnapshot",
    ...
]
```

### 4. Alembic Migration

**Файл**: `alembic/versions/c7a358fd3228_add_evaluation_snapshots.py`

Создана через:
```bash
alembic revision --autogenerate -m "add evaluation snapshots"
alembic upgrade head
```

**Индексы**:
- `idx_evaluation_snapshots_document_created` - (document_id, created_at)
- `idx_evaluation_snapshots_readiness_level` - readiness_level
- `idx_evaluation_snapshots_scoring_version` - scoring_version
- `ix_evaluation_snapshots_document_id` - document_id

### 5. Sync Engine

Добавлен в `app/db/session.py` для миграций и инспекции:

```python
from sqlalchemy import create_engine as create_sync_engine

sync_engine = create_sync_engine(
    settings.database_url.replace("+asyncpg", ""),
    echo=settings.app_debug,
)
```

## Schema Verification

```
evaluation_snapshots columns:
  id: UUID
  document_id: UUID
  overall_score: DOUBLE PRECISION
  ats_score: DOUBLE PRECISION
  evidence_score: DOUBLE PRECISION
  coverage_score: DOUBLE PRECISION
  quality_score: DOUBLE PRECISION
  readiness_level: VARCHAR(50)
  scoring_version: VARCHAR(50)
  blockers_json: JSON
  warnings_json: JSON
  metadata_json: JSON
  created_at: TIMESTAMP
```

## Benefits

1. **Audit trail**: Все оценки сохраняются в БД
2. **Comparison**: Можно сравнивать snapshots во времени
3. **Rollback**: Можно откатиться к предыдущей оценке
4. **Diff versions**: Можно сравнивать scoring versions

## Test Coverage

266 тестов пройдено ✅

## Usage Example

```python
from app.models import EvaluationSnapshot
from app.domain.readiness_evaluation import ReadinessEvaluation

# Создать snapshot из оценки
snapshot = EvaluationSnapshot(
    document_id=document_uuid,
    overall_score=evaluation.overall_score,
    ats_score=evaluation.ats_score,
    evidence_score=evaluation.evidence_score,
    coverage_score=evaluation.coverage_score,
    quality_score=evaluation.quality_score,
    readiness_level=evaluation.readiness_level.value,
    scoring_version="v1.0",
    blockers_json=evaluation.blockers,
    warnings_json=evaluation.warnings,
    metadata_json=evaluation.metadata,
)

session.add(snapshot)
await session.commit()

# Получить все snapshots для документа
snapshots = await session.execute(
    select(EvaluationSnapshot)
    .where(EvaluationSnapshot.document_id == document_uuid)
    .order_by(EvaluationSnapshot.created_at.desc())
)
```
