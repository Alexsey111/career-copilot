# Readiness Evaluation Integration

## Overview

`ReadinessEvaluation` теперь используется вместо `dict[str, float]` в:
- `ReviewActionLoop`
- `RecommendationExecutor`
- `MetricsAggregator`

## Changes

### app/services/review_action_loop.py

**До**:
```python
async def _get_current_readiness_score(self, document_id: UUID) -> dict[str, float]:
    return {
        "overall": 0.0,
        "ats": 0.0,
        "evidence": 0.0,
        "coverage": 0.0,
        "quality": 0.0,
    }

def _compute_readiness_delta(
    self,
    before: dict[str, float],
    after: dict[str, float],
) -> ReadinessDelta:
    ...
```

**После**:
```python
from app.domain.readiness_evaluation import ReadinessEvaluation

async def _get_current_readiness_score(self, document_id: UUID) -> ReadinessEvaluation:
    return ReadinessEvaluation(
        overall_score=0.0,
        ats_score=0.0,
        evidence_score=0.0,
        coverage_score=0.0,
        quality_score=0.0,
        readiness_level="not_ready",
        scoring_version="v1.0",
        evaluated_at=datetime.now(),
    )

def _compute_readiness_delta(
    self,
    before: ReadinessEvaluation,
    after: ReadinessEvaluation,
) -> ReadinessDelta:
    return ReadinessDelta(
        before_overall=before.overall_score,
        after_overall=after.overall_score,
        delta=after.overall_score - before.overall_score,
        before_components={
            "ats": before.ats_score,
            "evidence": before.evidence_score,
            "coverage": before.coverage_score,
            "quality": before.quality_score,
        },
        ...
    )
```

### app/services/metrics_aggregator.py

**До**:
```python
readiness = e.artifacts.get("readiness_score", {})
if isinstance(readiness, dict):
    ats = readiness.get("ats_score", 0.0)
    ...
```

**После**:
```python
from app.domain.readiness_evaluation import ReadinessEvaluation, ReadinessLevel

readiness_data = e.artifacts.get("readiness_evaluation") or e.artifacts.get("readiness_score", {})

if isinstance(readiness_data, ReadinessEvaluation):
    evaluation = readiness_data
    ats_scores.append(evaluation.ats_score)
    if evaluation.readiness_level == ReadinessLevel.READY:
        ready_count += 1
elif isinstance(readiness_data, dict):
    # Fallback for backward compatibility
    ...
```

## Benefits

1. **Type Safety**: IDE type hints работают корректно
2. **No circular imports**: Все импорты проверены
3. **Backward compatible**: Поддержка dict формата сохранена
4. **Structured data**: ReadinessEvaluation содержит больше полей (blockers, warnings, metadata)

## Testing

Все 79 тестов прошли:
```
tests/evals/test_artifact_registry.py        - 24 passed
tests/evals/test_retry_policy.py             - 19 passed
tests/evals/test_review_action_loop.py       - 15 passed
tests/evals/test_execution_metrics.py        - 21 passed
```

## Exports

`ReadinessEvaluation` экспортируется из:
- `app.domain` → `from app.domain import ReadinessEvaluation`
- `app.services` → `from app.services import ReadinessEvaluation`
