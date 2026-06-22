# Interview Prep Contract

## Purpose

Interview prep is a coaching artifact, not a factual claim.

The backend may suggest questions, evidence, and draft answers, but it must keep the grounding state explicit and conservative.

## Stable Question Categories

The API may emit these stable question categories:

- `technical`
- `behavioral`
- `leadership`
- `project_deep_dive`
- `gap-risk`
- `evidence_probe`

Category meaning:

- `technical` maps to a concrete vacancy requirement or tool.
- `behavioral` maps to a soft skill or working style signal.
- `leadership` covers coordination, ownership, mentoring, and decision-making.
- `project_deep_dive` drills into a confirmed achievement or project.
- `gap-risk` surfaces a missing or weak requirement and must stay honest.
- `evidence_probe` asks for more detail on a selected fact or achievement.

## Question Payload Contract

Question payloads should be treated as stable when they include:

- `question_id`
- `category`
- `prompt`
- `answer_format`
- `competency_key`
- `competency_name`
- `source_type`
- `source_requirement`
- `source_achievement_id`
- `fact_status`
- `requires_careful_answer`
- `recommended_evidence_ids`
- `recommended_evidence`
- `suggested_answer`
- `provenance`

`recommended_evidence` entries may include:

- `achievement_id`
- `title`
- `score`
- `reason`
- `source_type`
- `fact_status`
- `skills`
- `match_confidence`
- `match_type`

## Grounding Status

`questions[].suggested_answer.grounding_status` is a contract field and must remain stable.

Supported values:

- `grounded`
- `partial_evidence`
- `needs_confirmation`
- `insufficient_evidence`

Semantics:

- `grounded` means there is enough confirmed evidence to build a safe STAR draft.
- `partial_evidence` means there is some relevant evidence, but STAR is incomplete.
- `needs_confirmation` means the evidence may be relevant, but ownership or fact status still needs review.
- `insufficient_evidence` means there is no usable evidence for a safe draft.

Consumers must not treat any non-`grounded` answer as a verified claim.

## Evidence Match Confidence

`recommended_evidence[].match_confidence` is a deterministic ranking signal, not a truth score.

Supported values:

- `high`
- `medium`
- `low`

Meaning:

- `high` means the evidence is strongly aligned with the question and has enough support to surface first.
- `medium` means the evidence is usable, but less direct or less complete.
- `low` means the evidence is too weak for deterministic selection in most cases.

For behavioral questions, evidence should not be auto-selected unless the match is genuinely strong.

## Known Limitations

- STAR drafts may be partial. If situation, task, action, or result is missing, the answer should stay explicit about what still needs confirmation.
- Behavioral signals can still be generic. If the system cannot find a real match, it should not invent one.
- The system must not auto-claim experience from weak textual overlap alone.
- Gap-risk questions are diagnostic and should use human labels, not internal backend diagnostics.
- Internal source codes, extraction identifiers, and model-internal debug strings should not be shown to candidates.

## UI Guidance

The UI should show:

- human-readable source labels instead of internal source values;
- human-readable fact status labels;
- question category labels;
- honest gap wording for `gap-risk`;
- a visible caution when grounding is not `grounded`.

If the UI cannot explain why a question or answer was selected in human terms, it should not surface internal debug text to the candidate.
