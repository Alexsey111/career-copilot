# Recommendation Categories

## Overview

Замена fragile text parsing на typed `RecommendationCategory` enum.

## Проблема

**До**:
```python
# Fragile text parsing
message_lower = recommendation.message.lower()
if "metric" in message_lower:
    task_type = RecommendationTaskType.ADD_METRIC
elif "evidence" in message_lower:
    task_type = RecommendationTaskType.ADD_EVIDENCE
```

**Проблемы**:
- Хрупкое к изменениям текста
- Сложно поддерживать
- Нет type safety
- Трудно тестировать

## Решение

Добавлен `RecommendationCategory` enum:

```python
class RecommendationCategory(str, Enum):
    MISSING_METRIC = "missing_metric"
    WEAK_EVIDENCE = "weak_evidence"
    LOW_COVERAGE = "low_coverage"
    MISSING_CONTEXT = "missing_context"
    VAGUE_DESCRIPTION = "vague_description"
    ATS_PRESERVATION = "ats_preservation"
    STRUCTURE_IMPROVEMENT = "structure_improvement"
    GENERAL = "general"
```

## Обновление RecommendationItem

**До**:
```python
@dataclass
class RecommendationItem:
    message: str
    category: str = ""  # ❌ Строка
    severity: str = "info"
```

**После**:
```python
@dataclass
class RecommendationItem:
    message: str
    category: RecommendationCategory = RecommendationCategory.GENERAL  # ✅ Typed enum
    severity: str = "info"
```

## Использование в RecommendationTaskService

**До**:
```python
def _generate_task_from_recommendation(self, recommendation: RecommendationItem):
    message_lower = recommendation.message.lower()
    
    if "evidence" in message_lower and ("weak" in message_lower or "missing" in message_lower):
        pattern = self.task_patterns["weak_evidence"]
    elif "metric" in message_lower or "quantifiable" in message_lower:
        pattern = self.task_patterns["missing_metrics"]
    # ... больше 10 if/elif
```

**После**:
```python
def _generate_task_from_recommendation(self, recommendation: RecommendationItem):
    match recommendation.category:
        case RecommendationCategory.WEAK_EVIDENCE:
            pattern = self.task_patterns["weak_evidence"]
        case RecommendationCategory.MISSING_METRIC:
            pattern = self.task_patterns["missing_metrics"]
        case RecommendationCategory.LOW_COVERAGE:
            pattern = {
                "task_type": RecommendationTaskType.ADD_SKILL_KEYWORD,
                "priority": RecommendationPriority.HIGH,
                # ...
            }
        case RecommendationCategory.GENERAL:
            pattern = self.task_patterns["weak_evidence"]
```

## Преимущества

1. **Type safety**: IDE type hints работают корректно
2. **Maintainability**: Легко добавлять новые категории
3. **Testability**: Простое тестирование каждой категории
4. **No text parsing**: Надёжное определение типа рекомендации

## Backward Compatibility

Сервисы поддерживают как enum, так и строки (через Python enum):

```python
# Still works
category = RecommendationCategory("missing_metric")  # ✅

# Serialization to JSON
category.value  # "missing_metric" ✅

# Deserialization from JSON
RecommendationCategory("missing_metric")  # ✅
```

## Примеры использования

### ReadinessScoringService
```python
recommendations.append(RecommendationItem(
    message="Add quantifiable results",
    category=RecommendationCategory.MISSING_METRIC,
    severity="warning",
))
```

### RecommendationPrioritizationService
```python
IMPACT_PATTERNS = {
    RecommendationCategory.LOW_COVERAGE: {
        "score_delta": 0.15,
        "confidence": 0.9,
        "components": ["coverage", "evidence", "ats"],
    },
    RecommendationCategory.WEAK_EVIDENCE: {
        "score_delta": 0.12,
        "confidence": 0.85,
        "components": ["coverage", "evidence"],
    },
    # ...
}
```

## Serialization

```python
# To JSON
import json
data = {
    "category": recommendation.category.value,  # "missing_metric"
    "severity": recommendation.severity,
    "message": recommendation.message,
}

# From JSON
category = RecommendationCategory(data["category"])
```

## Test Coverage

**До**: 264 теста  
**После**: 266 тестов (+2 новых)

Все тесты проходят ✅

## Migration Guide

### Шаг 1: Заменить строки на enum
```python
# Before
RecommendationItem(message="...", category="evidence")

# After  
RecommendationItem(message="...", category=RecommendationCategory.WEAK_EVIDENCE)
```

### Шаг 2: Обновить pattern matching
```python
# Before
if "metric" in message.lower(): ...

# After
match recommendation.category:
    case RecommendationCategory.MISSING_METRIC: ...
```

### Шаг 3: Обновить тесты
```python
# Before
assert rec.category == "critical"

# After
assert rec.category == RecommendationCategory.LOW_COVERAGE
```

## Categories Map

| Category | Task Type | Priority | Description |
|----------|-----------|----------|-------------|
| `MISSING_METRIC` | `ADD_METRIC` | HIGH | Добавить количественные результаты |
| `WEAK_EVIDENCE` | `ADD_EVIDENCE` | HIGH | Усилить доказательства |
| `LOW_COVERAGE` | `ADD_SKILL_KEYWORD` | HIGH | Добавить ключевые слова |
| `MISSING_CONTEXT` | `ADD_CONTEXT` | MEDIUM | Добавить контекст |
| `VAGUE_DESCRIPTION` | `IMPROVE_DESCRIPTION` | MEDIUM | Уточнить описание |
| `ATS_PRESERVATION` | `ADD_SKILL_KEYWORD` | MEDIUM | Добавить ATS keywords |
| `STRUCTURE_IMPROVEMENT` | `IMPROVE_DESCRIPTION` | LOW | Улучшить структуру |
| `GENERAL` | `ADD_EVIDENCE` | MEDIUM | Общее улучшение |
