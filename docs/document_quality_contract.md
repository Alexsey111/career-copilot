# Document Quality Contract

This document fixes the public `quality` shape returned by review-summary APIs.
It is intentionally narrow: the goal is to keep the Quality Intelligence layer
stable across future PRs.

## Scope

The contract applies to:

- `GET /api/v1/documents/{document_id}/review-summary`
- `GET /api/v1/review/summary/document/{entity_id}`

Consumers may rely on the following `quality` fields being present when quality
analysis is available:

- `quality.score`
- `quality.score_breakdown`
- `quality.recommendations`
- `quality.roadmap`
- `quality.recommendations[].impact`
- `quality.recommendations[].details`

## `quality`

`quality` is a JSON object produced by `DocumentQualityService`.

Required top-level fields:

- `score`: integer document quality score in the `0..100` range.
- `score_breakdown`: ordered list of metric rows.
- `recommendations`: ordered list of improvement recommendations.
- `roadmap`: improvement plan derived from recommendations, or `null` when no
  actionable roadmap exists.

## `quality.score_breakdown`

Each item in `score_breakdown` contains:

- `code`: stable metric identifier.
- `label`: human-readable metric label.
- `score`: current metric score.
- `max_score`: metric ceiling.
- `missing_points`: `max_score - score`, clamped to `>= 0`.

The list is rendered in descending order of `missing_points` in the UI.

## `quality.recommendations`

Each recommendation item contains:

- `code`: stable recommendation identifier.
- `title`: human-readable recommendation title.
- `why`: short explanation of the problem.
- `actions`: actionable guidance list.
- `metric`: metric identifier that the recommendation affects.
- `impact`: stable impact object.
- `details`: stable diagnostics object.

### `quality.recommendations[].impact`

The `impact` object is used for ranking and roadmap building.

Required fields:

- `metric`: the affected metric identifier.
- `potential_gain`: optimistic expected score gain, integer `>= 0`.

### `quality.recommendations[].details`

`details` is a diagnostics container. The exact nested shape depends on the
recommendation type, but the object itself must remain present.

Current stable diagnostic blocks include:

- `vacancy_gap_diagnostics`
- `achievement_diagnostics`

## `quality.roadmap`

`roadmap` is either `null` or an object with:

- `current_score`: current overall score.
- `projected_score`: optimistic score after the first prioritized improvement.
- `steps`: ordered improvement steps.

Each roadmap step contains:

- `order`: 1-based step order.
- `title`: human-readable step title.
- `expected_gain`: optimistic score gain for the step.

## Example

```json
{
  "score": 67,
  "score_breakdown": [
    {
      "code": "vacancy_alignment",
      "label": "Соответствие вакансии",
      "score": 10,
      "max_score": 25,
      "missing_points": 15
    }
  ],
  "recommendations": [
    {
      "code": "improve_vacancy_alignment",
      "title": "Усилить соответствие вакансии",
      "why": "Документ слабо покрывает требования вакансии.",
      "actions": ["Добавить только подтверждённые навыки."],
      "metric": "vacancy_alignment",
      "impact": {
        "metric": "vacancy_alignment",
        "potential_gain": 25
      },
      "details": {
        "vacancy_gap_diagnostics": {
          "total_missing": 2
        }
      }
    }
  ],
  "roadmap": {
    "current_score": 67,
    "projected_score": 92,
    "steps": [
      {
        "order": 1,
        "title": "Усилить соответствие вакансии",
        "expected_gain": 25
      }
    ]
  }
}
```
