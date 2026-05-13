# ReadinessEvaluationService

## Overview

`ReadinessEvaluationService` — чистый сервис для вычисления и сохранения readiness оценок.

## Responsibility

**ТОЛЬКО**:
- calculate evaluation
- return canonical `ReadinessEvaluation` object
- persist snapshot to database

**НИКАКОГО**:
- recommendation execution
- document mutation
- review logic

## Architecture

```
ReadinessEvaluationService
├── ReadinessScoringService (dependency)
│   └── calculate_readiness() → ReadinessScore
├── DocumentVersionRepository (dependency)
│   └── get_by_id() → DocumentVersion
└── EvaluationSnapshot (persistence)
    └── save() → EvaluationSnapshot
```

## Interface

```python
class ReadinessEvaluationService:
    async def evaluate_document(
        self,
        session: AsyncSession,
        document_id: UUID,
        user_id: UUID,
    ) -> ReadinessEvaluation:
        """
        Вычисляет readiness evaluation для документа и сохраняет snapshot.
        
        Returns:
            ReadinessEvaluation с результатами оценки
        """
```

## Usage Example

```python
from app.services.readiness_evaluation_service import ReadinessEvaluationService
from app.services.readiness_scoring_service import ReadinessScoringService
from app.repositories.document_version_repository import DocumentVersionRepository

# Initialize
scoring_service = ReadinessScoringService(
    coverage=coverage_data,
    evidence_scores=evidence_scores,
    ats_preservation_score=ats_score,
)
doc_repository = DocumentVersionRepository()
evaluation_service = ReadinessEvaluationService(
    scoring_service=scoring_service,
    document_repository=doc_repository,
)

# Evaluate document
async with db_session() as session:
    evaluation = await evaluation_service.evaluate_document(
        session=session,
        document_id=document_uuid,
        user_id=user_uuid,
    )
    
    print(f"Overall: {evaluation.overall_score}")
    print(f"Level: {evaluation.readiness_level}")
    print(f"Blockers: {evaluation.blockers}")
    
    # Snapshot automatically saved to database
    snapshot = await evaluation_service.get_latest_snapshot(
        session=session,
        document_id=document_uuid,
    )
```

## ReadinessEvaluation Object

```python
@dataclass
class ReadinessEvaluation:
    overall_score: float
    
    # Component scores
    ats_score: float
    evidence_score: float
    coverage_score: float
    quality_score: float
    
    readiness_level: ReadinessLevel  # READY | NEEDS_WORK | NOT_READY
    
    scoring_version: str
    evaluated_at: datetime
    
    components: list[ComponentScore]
    blockers: list[str]
    warnings: list[str]
    metadata: dict[str, str]
```

## Component Explanations

Service automatically generates explanations for each component:

| Component | Score Range | Explanation |
|-----------|-------------|-------------|
| ATS | ≥ 0.8 | Excellent keyword preservation |
| ATS | 0.6-0.8 | Good keyword preservation with minor gaps |
| ATS | 0.4-0.6 | Moderate keyword preservation |
| ATS | < 0.4 | Poor keyword preservation |
| Evidence | ≥ 0.8 | Strong quantifiable evidence throughout |
| Evidence | 0.6-0.8 | Good evidence with some areas for improvement |
| Evidence | 0.4-0.6 | Limited quantifiable proof |
| Evidence | < 0.4 | Weak evidence |
| Coverage | ≥ 0.8 | Comprehensive coverage of requirements |
| Coverage | 0.6-0.8 | Good coverage with some gaps |
| Coverage | 0.4-0.6 | Partial coverage |
| Coverage | < 0.4 | Insufficient coverage |

## Persistence

`EvaluationSnapshot` automatically saved to database:

```sql
INSERT INTO evaluation_snapshots (
    document_id,
    overall_score,
    ats_score,
    evidence_score,
    coverage_score,
    quality_score,
    readiness_level,
    scoring_version,
    blockers_json,
    warnings_json,
    metadata_json,
    created_at
) VALUES (...);
```

## Benefits

1. **Separation of concerns**: Evaluation logic separated from mutation logic
2. **Testability**: Easy to test evaluation without side effects
3. **Audit trail**: All evaluations persisted for comparison
4. **Versioning**: Scoring version tracked for reproducibility

## Integration Points

### ReviewActionLoop
```python
# Before: placeholder calls
before_score = await self._get_current_readiness_score(document_id)

# After: use service
evaluation = await evaluation_service.evaluate_document(
    session=session,
    document_id=document_id,
    user_id=user_id,
)
```

### MetricsAggregator
```python
# Can now query snapshots for metrics
snapshot = await evaluation_service.get_latest_snapshot(
    session=session,
    document_id=document_id,
)
```

## Tests

266 tests passed ✅
