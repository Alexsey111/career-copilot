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

Product wording may sometimes use `gap_risk`, but the API payload currently emits `gap-risk`.

Category meaning:

- `technical` maps to a concrete vacancy requirement or tool.
- `behavioral` maps to a soft skill or working style signal.
- `leadership` covers coordination, ownership, mentoring, and decision-making.
- `project_deep_dive` drills into a confirmed achievement or project.
- `gap-risk` surfaces a missing or weak requirement and must stay honest.
- `evidence_probe` asks for more detail on a selected fact or achievement.

## Stable Case Types

The case-prep endpoint (`GET /api/v1/interview-prep/cases/{vacancy_id}`) may emit these stable case types:

- `system_design`
- `debugging_scenario`
- `data_analysis`
- `behavioral_case`
- `take_home_brief`

Case meaning:

- `system_design` — design a system for the area implied by a requirement; outline components, data flow, trade-offs, failure modes. Framework: `hypothesis-driven`.
- `debugging_scenario` — investigate a degraded service related to a requirement; form hypotheses and probes. Framework: `hypothesis-driven`.
- `data_analysis` — define an analysis touching a requirement: question, metrics, segmentation, conclusion. Framework: `structured_walkthrough`.
- `behavioral_case` — describe a concrete situation from your own experience addressing a requirement, using STAR with a quantified result. Framework: `STAR`.
- `take_home_brief` — a short take-home exercising a requirement: clarify scope, deliver the core path, cover edge cases, document trade-offs. Framework: `RTL`.

Each case payload is stable when it includes:

- `case_id`
- `case_type`
- `title`
- `prompt`
- `framework`
- `time_guidance`
- `rubric`
- `suggested_approach`
- `recommended_evidence`
- `competency_key`
- `source_requirement`
- `gap_severity`
- `provenance`

### Case Factuality Rules

- Cases are **templates, not live scenarios**: the `prompt` is parameterised only by a requirement/gap keyword and must not invent specific companies, numbers, or names.
- `recommended_evidence` is reused from `VacancyFitService.build_vacancy_fit` supporting evidence and is filtered to `fact_status` in `{confirmed, user_provided}` (stricter than `usable_matches`, which also admits `needs_confirmation`) — a practice case must rest on confirmed STAR.
- `time_guidance` is a band (`15-30 minutes`, `60-90 minutes`, `2-4 hours, take-home`), never a concrete deadline or date.
- The system must not fabricate evidence, metrics, or named stakeholders for a case.

### Case Human Review Rules

- `provenance.requires_human_review` is always `true`.
- The candidate is expected to adapt the template scenario to the actual prompt received from the employer; the case is a preparation artifact, not a model answer.
- Human review is required even when recommended evidence is present.

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

## Evidence Rules

- `technical` questions may only attach evidence with `match_type` values `exact_requirement` or `keyword_overlap`.
- `behavioral` questions may only attach evidence with `match_confidence = high`.
- `gap-risk` questions must never fabricate evidence.
- `project_deep_dive` questions should surface the strongest available evidence, but still only from real evidence candidates.

The system must not promote weak textual overlap into a supported claim.

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

## Human Review Rules

- `suggested_answer.requires_human_review` is always `true`.
- This flag is part of the contract for every suggested answer, including grounded drafts.
- Human review is required even when the draft looks complete, because the answer remains a preparation artifact.

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

- Interview Prep does not invent experience.
- If confirmed evidence is missing, the system still creates the question and a preparation draft, but it does not attach evidence and readiness should decrease.
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

## Answer Rubric Scoring

The answer-scoring endpoints (`POST /api/v1/interview-prep/cases/{vacancy_id}/answers`, `GET .../attempts`, `GET .../progress`) score a candidate's answer to a practice case **per criterion** against the stable rubric (`build_rubric(case_type)` — 5 criteria per case type).

Scoring is **deterministic keyword-heuristic, no AI**:

- For each criterion, the backend counts how many of that criterion's marker terms appear in the answer (casefold substring). `score = min(3, count of unique matched markers)`.
- `level`: `0 → none`, `1 → low`, `2 → medium`, `3 → high`. `high` means the expected vocabulary is present — **not** that the answer is correct.
- `overall_score = round(sum(scores) / count_criteria * 100 / 3, 1)` (0..100).
- `grade`: `>=85 excellent`, `>=70 good`, `>=50 needs_work`, else `weak`.
- `rubric_version` is stable (`deterministic_v1`); stable criterion keys are the exact strings from `build_rubric(case_type)`.
- `criterion_scores[].reason` references **marker-term names**, never substrings of the candidate's answer — the answer is personal data and must not leak into the JSON response.
- `feedback`: `strengths` (criteria scored `high`), `improvements` (`Address: <criterion>` for `none`/`low`), `issues` (coaching note when `overall < 50` or the answer is empty).

Human review and privacy:

- `requires_human_review` is always `true`: the score is a coaching artifact (does the right vocabulary appear), not a verdict on correctness, depth, or truth.
- Human review is required even when `overall_score` is high.
- `answer_text` is personal data and is stored encrypted at rest (`EncryptedText`, ФЗ-152 ст.19) in `interview_prep_answer_attempts`; `criterion_scores_json`, `grade`, `overall_score`, and `feedback_json` are not personal data and are stored as plain JSON.
- The backend does not verify the factual truth or depth of the answer; scoring only checks vocabulary presence.

## Cross-Session Progress

`GET /api/v1/interview-prep/cases/{vacancy_id}/progress?case_id=...` returns a **backward-looking snapshot** of a candidate's attempts at one practice case (ordered `created_at` ascending):

- `total_attempts`
- `overall`: `{first, last, best, improvement, trend}` (0..100; `improvement = round(last - first, 1)`; `trend`: `improving` when `improvement > 1.0`, `declining` when `< -1.0`, else `stable`)
- `per_criterion[]`: `{criterion, first, last, best, improvement}` on the 0..3 scale; `best` is the max across all attempts

Empty case (no attempts yet):

- `total_attempts: 0`, `reason: "no attempts yet"`, `overall: null`, `per_criterion: []`.

Non-goals:

- The snapshot is backward-looking only. It must not emit `forecast`, `predicted`, or `probability` values, nor a numeric projection of future progress.
- The `trend` label is coarse (`improving` / `declining` / `stable`) and is not a prediction.
