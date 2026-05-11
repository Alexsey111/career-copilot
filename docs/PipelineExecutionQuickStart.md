# Pipeline Execution Tracking - Quick Start

## Quick Summary

Добавлена система отслеживания выполнения pipeline с тремя основными таблицами:

1. **`pipeline_executions`** - основные записи выполнения
2. **`pipeline_execution_steps`** - детальные шаги внутри execution
3. **`pipeline_events`** - структурированные события для observability

## Files Created/Modified

### New Files

- `app/domain/pipeline_models.py` - Domain models (CareerCopilotRun, PipelineExecutionStep, PipelineEvent)
- `app/models/entities.py` - Добавлены 3 новые SQLAlchemy модели
- `app/repositories/pipeline_repository.py` - Repository для работы с БД
- `app/services/pipeline_execution_service.py` - Бизнес-логика
- `app/schemas/pipeline_schemas.py` - Pydantic схемы для API
- `app/api/routes/pipeline_execution_routes.py` - FastAPI endpoints
- `alembic/versions/8a2b36d82e8a_add_pipeline_execution_tables.py` - Migration
- `tests/test_pipeline_execution.py` - Юнит тесты
- `docs/PipelineExecutionTracking.md` - Полная документация

### Modified Files

- `app/models/__init__.py` - Экспорт новых моделей
- `app/api/router.py` - Подключение новых роутов

## Quick Usage Example

```python
from app.services.pipeline_execution_service import PipelineExecutionService
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository

# Init
repository = SQLAlchemyAsyncPipelineRepository(session=db)
service = PipelineExecutionService(repository=repository)

# Start pipeline
execution = await service.start_execution(
    user_id=user_id,
    vacancy_id=vacancy_id,
    pipeline_version="v1.0",
)

# Track steps
step = await service.start_step(execution.id, "extract_features")
# ... do work ...
await service.complete_step(step.id, output_artifact_ids=["feat_123"])

# Complete
await service.complete_execution(
    execution.id,
    artifacts={"resume": "doc_123"},
    metrics={"score": 0.95},
)
```

## API Endpoints

```
POST   /api/v1/pipeline/executions              # Create execution
GET    /api/v1/pipeline/executions/{id}         # Get summary
GET    /api/v1/pipeline/executions/user/{id}    # User executions
GET    /api/v1/pipeline/executions/vacancy/{id} # Vacancy executions
```

## Database Schema

```sql
-- Main execution table
pipeline_executions (
    id, user_id, vacancy_id, profile_id,
    status, pipeline_version, calibration_version,
    started_at, completed_at, failed_at,
    resume_document_id, evaluation_snapshot_id, review_id,
    error_code, error_message,
    artifacts_json, metrics_json,
    created_at, updated_at
)

-- Step tracking
pipeline_execution_steps (
    id, execution_id, step_name,
    status, started_at, completed_at, duration_ms,
    input_artifact_ids, output_artifact_ids,
    error_message, metadata_json,
    created_at, updated_at
)

-- Event logging
pipeline_events (
    id, execution_id, step_id,
    event_type, payload_json, severity,
    created_at
)
```

## Key Features

✅ **Resume capability** - Можно возобновить с любой точки
✅ **Debugging** - Детальные логи всех шагов
✅ **Dashboard data** - Все метрики для аналитики
✅ **Retries** - Поддержка повторных попыток
✅ **Lineage** - Отслеживание происхождения артефактов
✅ **History** - История для пользователя

## Next Steps

1. Интегрировать в существующие workflows
2. Добавить UI для отображения истории
3. Настроить мониторинг и алерты
4. Добавить export для аналитики

## Testing

```bash
# Run pipeline tests
pytest tests/test_pipeline_execution.py -v

# Run migrations
alembic upgrade head
```

## Migration Status

✅ Migration created: `8a2b36d82e8a_add_pipeline_execution_tables.py`
✅ Migration applied: Database updated successfully
