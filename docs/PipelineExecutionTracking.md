# Pipeline Execution Tracking System

## Overview

Система отслеживания выполнения pipeline для career-copilot. Обеспечивает:

- **Восстановление pipeline** - возможность возобновить выполнение с любой точки
- **Debugging** - детальные логи и трассировка выполнения
- **Dashboard** - данные для построения аналитики
- **Retries** - поддержка повторных попыток выполнения
- **Lineage** - отслеживание происхождения артефактов
- **History** - история выполнений для пользователя

## Architecture

### Database Tables

#### 1. `pipeline_executions` - основная таблица

Хранит информацию о каждом выполнении pipeline:

```sql
id                    UUID PRIMARY KEY
user_id               UUID REFERENCES users(id)
vacancy_id            UUID REFERENCES vacancies(id)
profile_id            UUID REFERENCES candidate_profiles(id)
status                VARCHAR(50) -- pending, running, completed, failed, cancelled
pipeline_version      VARCHAR(50)
calibration_version   VARCHAR(50)
started_at            TIMESTAMP
completed_at          TIMESTAMP
failed_at             TIMESTAMP
resume_document_id    UUID REFERENCES document_versions(id)
evaluation_snapshot_id UUID REFERENCES vacancy_analyses(id)
review_id             UUID REFERENCES document_reviews(id)
error_code            VARCHAR(100)
error_message         TEXT
artifacts_json        JSONB
metrics_json          JSONB
created_at            TIMESTAMP
updated_at            TIMESTAMP
```

**Индексы:**
- `idx_pipeline_executions_user_status` - для быстрого поиска по пользователю и статусу
- `idx_pipeline_executions_vacancy_status` - для поиска по вакансии
- `idx_pipeline_executions_profile_status` - для поиска по профилю

#### 2. `pipeline_execution_steps` - шаги выполнения

Хранит детали каждого шага внутри pipeline:

```sql
id                    UUID PRIMARY KEY
execution_id          UUID REFERENCES pipeline_executions(id)
step_name             VARCHAR(100)
status                VARCHAR(50) -- pending, running, completed, failed, skipped
started_at            TIMESTAMP
completed_at          TIMESTAMP
duration_ms           INTEGER
input_artifact_ids    JSONB -- массив ID входных артефактов
output_artifact_ids   JSONB -- массив ID выходных артефактов
error_message         TEXT
metadata_json         JSONB
created_at            TIMESTAMP
updated_at            TIMESTAMP
```

**Индексы:**
- `idx_pipeline_execution_steps_execution_name` - композитный индекс для поиска шагов

#### 3. `pipeline_events` - структурированные события

Хранит события выполнения pipeline:

```sql
id                    UUID PRIMARY KEY
execution_id          UUID REFERENCES pipeline_executions(id)
event_type            VARCHAR(50) -- см. типы событий ниже
step_id               UUID REFERENCES pipeline_execution_steps(id)
payload_json          JSONB
severity              VARCHAR(20) -- debug, info, warning, error
created_at            TIMESTAMP
```

**Типы событий:**
- `pipeline_started` - начало выполнения pipeline
- `pipeline_completed` - успешное завершение
- `pipeline_failed` - неудачное завершение
- `step_started` - начало выполнения шага
- `step_completed` - успешное завершение шага
- `step_failed` - неудачное завершение шага
- `evaluation_failed` - ошибка валидации/оценки
- `review_required` - требуется ручной ревью
- `recommendation_generated` - сгенерирована рекомендация

**Индексы:**
- `idx_pipeline_events_execution_type` - для поиска событий по execution и типу
- `idx_pipeline_events_type_severity` - для фильтрации по типу и серьезности

## Usage

### Basic Workflow

```python
from app.services.pipeline_execution_service import PipelineExecutionService
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from sqlalchemy.ext.asyncio import AsyncSession

# Инициализация
repository = SQLAlchemyAsyncPipelineRepository(session=db)
service = PipelineExecutionService(repository=repository)

# 1. Начать выполнение pipeline
execution = await service.start_execution(
    user_id=user_id,
    vacancy_id=vacancy_id,
    profile_id=profile_id,
    pipeline_version="v1.0",
    calibration_version="v2.1",
)

# 2. Начать шаг
step = await service.start_step(
    execution_id=execution.id,
    step_name="extract_resume_features",
    input_artifact_ids=["resume_123"],
)

# 3. Завершить шаг
await service.complete_step(
    step_id=step.id,
    output_artifact_ids=["features_456"],
    metadata={"processing_time_ms": 1500},
)

# 4. Завершить pipeline
await service.complete_execution(
    execution_id=execution.id,
    artifacts={"resume": "doc_123", "cover_letter": "doc_456"},
    metrics={"match_score": 0.85, "quality_score": 0.92},
    resume_document_id=document_id,
)
```

### Error Handling

```python
try:
    # Выполнение pipeline...
    pass
except Exception as e:
    await service.fail_execution(
        execution_id=execution.id,
        error_code="EXTRACTION_FAILED",
        error_message=str(e),
        artifacts={"partial": partial_data},
    )
```

### Recording Events

```python
# Оценка не прошла
await service.record_evaluation_failed(
    execution_id=execution.id,
    step_id=step.id,
    error_details={"reason": "low_match_score", "score": 0.3},
)

# Требуется ревью
await service.record_review_required(
    execution_id=execution.id,
    review_reason="hallucinated_metrics_detected",
)

# Сгенерирована рекомендация
await service.record_recommendation_generated(
    execution_id=execution.id,
    recommendation_data={"type": "skill_gap", "suggestions": [...]},
)
```

## API Endpoints

### Create Pipeline Execution

```http
POST /api/v1/pipeline/executions
Content-Type: application/json

{
  "user_id": "uuid",
  "vacancy_id": "uuid",
  "profile_id": "uuid",
  "pipeline_version": "v1.0",
  "calibration_version": "v2.1"
}
```

### Get Execution Summary

```http
GET /api/v1/pipeline/executions/{execution_id}
```

Returns full summary with steps and events.

### Get User Executions

```http
GET /api/v1/pipeline/executions/user/{user_id}?limit=20&offset=0&status=completed
```

### Get Vacancy Executions

```http
GET /api/v1/pipeline/executions/vacancy/{vacancy_id}?limit=20&offset=0
```

## Domain Models

### CareerCopilotRun

```python
@dataclass
class CareerCopilotRun:
    id: str
    user_id: str
    vacancy_id: str
    profile_id: str
    resume_document_id: Optional[str]
    evaluation_snapshot_id: Optional[str]
    review_id: Optional[str]
    status: PipelineStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    pipeline_version: str
    calibration_version: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    artifacts: dict[str, Any]
    metrics: dict[str, Any]
    created_at: datetime
    updated_at: datetime
```

### PipelineExecutionStep

```python
@dataclass
class PipelineExecutionStep:
    id: str
    execution_id: str
    step_name: str
    status: StepStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    input_artifact_ids: list[str]
    output_artifact_ids: list[str]
    error_message: Optional[str]
    metadata: dict[str, Any]
```

### PipelineEvent

```python
@dataclass
class PipelineEvent:
    id: str
    execution_id: str
    event_type: PipelineEventType
    step_id: Optional[str]
    payload: dict[str, Any]
    severity: EventSeverity
    created_at: datetime
```

## Repository Pattern

Используется Repository pattern для абстракции над данными:

```python
class SQLAlchemyAsyncPipelineRepository:
    async def create_execution(...) -> CareerCopilotRun
    async def get_execution(...) -> Optional[CareerCopilotRun]
    async def get_execution_with_steps_and_events(...) -> Optional[PipelineExecutionSummary]
    async def update_execution(...) -> None
    async def create_step(...) -> PipelineExecutionStep
    async def update_step(...) -> None
    async def create_event(...) -> PipelineEvent
    async def get_executions_for_user(...) -> list[CareerCopilotRun]
    async def get_executions_for_vacancy(...) -> list[CareerCopilotRun]
```

## Best Practices

1. **Всегда начинайте с `start_execution()`** - создает запись в БД
2. **Записывайте события для важных операций** - для debugging и аналитики
3. **Используйте `artifacts_json` для хранения результатов** - JSON для гибкости
4. **Используйте `metrics_json` для количественных показателей** - для мониторинга
5. **Указывайте `error_code` при ошибках** - для классификации и retries
6. **Добавляйте `metadata_json` в шаги** - для детальной информации
7. **Используйте severity для событий** - debug, info, warning, error

## Monitoring & Dashboarding

Примеры SQL-запросов для аналитики:

```sql
-- Среднее время выполнения pipeline
SELECT AVG(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000) as avg_duration_ms
FROM pipeline_executions
WHERE status = 'completed';

-- Распределение по статусам
SELECT status, COUNT(*) as count
FROM pipeline_executions
GROUP BY status;

-- Частые ошибки
SELECT error_code, COUNT(*) as count, AVG(duration_ms) as avg_duration
FROM pipeline_executions
WHERE status = 'failed'
GROUP BY error_code
ORDER BY count DESC;

-- Время выполнения по шагам
SELECT step_name, AVG(duration_ms) as avg_duration_ms, COUNT(*) as executions
FROM pipeline_execution_steps
GROUP BY step_name
ORDER BY avg_duration_ms DESC;
```

## Files Structure

```
app/
├── domain/
│   └── pipeline_models.py          # Domain models (dataclasses, enums)
├── models/
│   ├── entities.py                 # SQLAlchemy models
│   └── __init__.py                 # Exports
├── repositories/
│   └── pipeline_repository.py      # Repository interface + implementation
├── services/
│   └── pipeline_execution_service.py # Business logic service
├── schemas/
│   └── pipeline_schemas.py         # Pydantic schemas for API
└── api/
    └── routes/
        └── pipeline_execution_routes.py # FastAPI endpoints

alembic/
└── versions/
    └── 8a2b36d82e8a_add_pipeline_execution_tables.py  # Migration
```
