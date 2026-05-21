# Interview Prep Provenance Contract

## Purpose

Interview prep output is coaching material, not verified truth.

Every generated question and recommendation must remain explainable through vacancy requirements, confirmed achievements, and deterministic matching logic.

## Where Stored

Interview prep provenance is stored in:

- `InterviewPrepSession.provenance`
- `InterviewPrepSession.readiness_json["provenance"]`
- `InterviewPrepSession.question_set_json[*]["provenance"]`
- exposed through `GET /api/v1/interview-prep/sessions/{id}`
- exposed through `GET /api/v1/interview-prep/sessions/{id}/readiness`

## Session-Level Provenance Fields

Session-level provenance may include:

- `source`
- `generation_mode`
- `application_id`
- `vacancy_id`
- `analysis_id`
- `selected_achievement_ids`
- `selected_evidence_ids`
- `competency_sources`
- `question_generation_mode`
- `question_source_counts`
- `confidence`
- `requires_human_review`

## Question-Level Provenance Fields

Question-level provenance may include:

- `source_type`
- `source_requirement`
- `source_achievement_id`
- `recommended_evidence_ids`
- `fact_status`
- `requires_careful_answer`
- `requires_human_review`

## Gap-Risk Semantics

`gap-risk` questions are generated when the matching logic detects missing or weak coverage for an important vacancy requirement.

They are intentionally framed as coaching prompts, not as factual claims about the candidate.

Recommended answers should:

- acknowledge the gap honestly;
- avoid pretending the skill is already confirmed;
- emphasize adjacent experience, learning effort, or mitigation strategy;
- remain suitable for human review before any external use.

## Human Review Invariant

Interview prep output must not be treated as final truth.

`requires_human_review=true` must be preserved for generated sessions and generated questions.

## API Exposure

Frontend clients should read provenance from:

1. `GET /api/v1/interview-prep/sessions/{id}`
2. `GET /api/v1/interview-prep/sessions/{id}/readiness`

Question provenance is available inside the session's `questions` payload.

## Backward Compatibility

Older interview prep payloads may not include explicit provenance fields.

Readers should use this fallback order:

1. `InterviewPrepSession.provenance`
2. `InterviewPrepSession.readiness_json["provenance"]`
3. `question_set_json[*]["provenance"]`
4. legacy question fields such as `source_type`, `fact_status`, and `recommended_evidence_ids`

## UX Guidance

Review UI should show:

- selected evidence ids and linked evidence snippets;
- selected achievements;
- question source type and source requirement;
- confidence;
- readiness warnings;
- gap-risk caution state;
- human review requirement.

UI copy should make it clear that interview prep is a guided coaching artifact and should not be presented as confirmed factual history.
