# DocumentMutationService

## Overview

`DocumentMutationService` — безопасное изменение документов через создание новых версий.

## Проблема

**До**:
```python
# Dangerous: direct update
document.content_json["summary"] = "New text"
await session.commit()
```

**Проблемы**:
- Нет истории изменений
- Нельзя откатиться
- Нет lineage tracking
- Race conditions

**После**:
```python
# Safe: create new version
new_document = await mutation_service.apply_changes(
    session=session,
    document_id=document_id,
    changes={"operations": [...]},
    user_id=user_id,
)
```

## Responsibility

**ТОЛЬКО**:
- create new document version
- apply structured patch
- maintain lineage

**НЕ**:
- ❌ update existing document
- ❌ evaluation logic
- ❌ recommendation generation

## Interface

```python
class DocumentMutationService:
    async def apply_changes(
        self,
        *,
        document_id: UUID,
        changes: dict,
        user_id: UUID,
        version_label: str | None = None,
        change_reason: str | None = None,
    ) -> DocumentVersion:
        """
        Применяет изменения к документу, создавая новую версию.
        
        НЕ UPDATE EXISTING DOCUMENT.
        Только: old version → new version
        """

    async def apply_recommendation(
        self,
        *,
        document_id: UUID,
        recommendation_id: str,
        changes: dict,
        user_id: UUID,
    ) -> DocumentVersion:
        """Конvenience method для применения рекомендаций."""
```

## Lineage Tracking

```sql
-- Исходный документ
INSERT INTO document_versions (id, version_label, is_active, ...)
VALUES ('doc-1', 'v1', TRUE, ...);

-- Новая версия (через mutation)
INSERT INTO document_versions (id, derived_from_id, version_label, is_active, ...)
VALUES ('doc-2', 'doc-1', 'v2', TRUE, ...);

-- Старая версия деактивирована
UPDATE document_versions SET is_active = FALSE WHERE id = 'doc-1';
```

## Structured Patch Format

```python
changes = {
    "operations": [
        # Set field value
        {
            "section": "summary",
            "operation": "set",
            "field": "text",
            "value": "New text"
        },
        
        # Append to string
        {
            "section": "summary",
            "operation": "append",
            "value": " - Added context"
        },
        
        # Add to list
        {
            "section": "skills",
            "operation": "add",
            "item": "Docker"
        },
        
        # Merge dict
        {
            "section": "profile",
            "operation": "merge",
            "extra": {"email": "john@example.com"}
        },
        
        # Remove from list
        {
            "section": "achievements",
            "operation": "remove",
            "index": 1
        }
    ]
}
```

## Supported Operations

| Operation | Section Type | Description |
|-----------|--------------|-------------|
| `set` | dict/list | Set field value |
| `append` | str/list | Append to string/list |
| `add` | list | Add item to list |
| `merge` | dict | Merge additional fields |
| `remove` | list | Remove item by index |

## Usage Example

### Apply Recommendation
```python
from app.services.document_mutation_service import DocumentMutationService

mutation_service = DocumentMutationService(document_repository=repo)

async with db_session() as session:
    new_document = await mutation_service.apply_recommendation(
        session=session,
        document_id=document_uuid,
        recommendation_id="rec-123",
        changes={
            "operations": [
                {
                    "section": "experience",
                    "index": 0,
                    "operation": "set",
                    "field": "company",
                    "value": "New Company Name"
                }
            ]
        },
        user_id=user_uuid,
    )
    
    print(f"Created version: {new_document.version_label}")
    print(f"Derived from: {new_document.derived_from_id}")
```

### Manual Changes
```python
new_document = await mutation_service.apply_changes(
    session=session,
    document_id=document_uuid,
    changes={
        "operations": [
            {"section": "summary", "operation": "append", "value": "New text"},
            {"section": "skills", "operation": "add", "item": "Python"},
        ]
    },
    user_id=user_uuid,
    version_label="v2",
    change_reason="User requested updates",
)
```

## Mutation History

Каждая mutation записывается в `mutation_history`:

```json
{
  "mutation_history": [
    {
      "timestamp": "2024-01-15T10:30:00",
      "changes": {...},
      "reason": "Applied recommendation: rec-123"
    },
    {
      "timestamp": "2024-01-15T11:45:00",
      "changes": {...},
      "reason": "Manual update"
    }
  ]
}
```

## Version Label Generation

```python
# Auto-increment
source: v1 → new: v2
source: v3 → new: v4

# Non-numeric
source: initial → new: initial-modified
source: draft → new: draft-modified
```

## Integration with ReviewActionLoop

```python
class RecommendationExecutor:
    def __init__(
        self,
        mutation_service: DocumentMutationService,
        evaluation_service: ReadinessEvaluationService,
    ):
        self._mutation_service = mutation_service
        self._evaluation_service = evaluation_service
    
    async def execute_recommendation(
        self,
        session: AsyncSession,
        recommendation_id: str,
        document_id: UUID,
        changes: dict,
        user_id: UUID,
    ):
        # 1. Get current evaluation
        before = await self._evaluation_service.evaluate_document(...)
        
        # 2. Apply changes (creates new version)
        new_document = await self._mutation_service.apply_recommendation(
            session=session,
            document_id=document_id,
            recommendation_id=recommendation_id,
            changes=changes,
            user_id=user_id,
        )
        
        # 3. Re-evaluate new version
        after = await self._evaluation_service.evaluate_document(
            session=session,
            document_id=new_document.id,
            ...
        )
        
        # 4. Compute delta
        delta = self._compute_evaluation_delta(before, after)
```

## Benefits

1. **Audit trail**: Полная история изменений
2. **Rollback**: Можно вернуться к любой версии
3. **Lineage**: Явная связь версий
4. **No race conditions**: Каждая mutation создаёт новую строку
5. **Safe**: Не затрагивает активные версии

## Test Coverage

11 тестов пройдено ✅

```
test_apply_patch_simple_set
test_apply_patch_append_string
test_apply_patch_append_list
test_apply_patch_add_to_list
test_apply_patch_merge_dict
test_apply_patch_remove_from_list
test_apply_patch_deep_copy
test_generate_version_label_increment
test_generate_version_label_custom
test_apply_patch_no_section
test_apply_patch_empty_changes
```

## Migration Guide

### Before (direct update)
```python
document.content_json["summary"] = "New"
await session.commit()
```

### After (version creation)
```python
new_document = await mutation_service.apply_changes(
    session=session,
    document_id=document.id,
    changes={"operations": [...]},
    user_id=user.id,
)
```
