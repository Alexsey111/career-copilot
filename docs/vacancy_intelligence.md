# Vacancy Intelligence

## Purpose

Vacancy Intelligence gives explainable operational guidance for deciding:

- which vacancies are worth spending time on;
- where the candidate has real gaps;
- whether the vacancy is ready to apply for now or should be deferred.

## Deterministic Signals

The fit breakdown is rule-based and deterministic. It uses already available backend signals:

- vacancy analysis keywords and requirement groups;
- profile and experience text overlap;
- confirmed evidence snippets;
- evidence strength;
- fact status;
- leadership and seniority signals.

## Endpoint

`GET /vacancies/{vacancy_id}/fit`

Returns an explainable fit payload with:

- overall fit score;
- fit dimensions;
- gap severity;
- readiness recommendation;
- evidence coverage.

## Fit Dimensions

The fit model is broken into:

- `overall_fit_score`
- `skills_fit`
- `evidence_fit`
- `experience_fit`
- `leadership_fit`

Each dimension is deterministic and derived from existing profile, vacancy analysis, and evidence data.

## Gap Severity

Gaps are classified into simple operational levels:

- `critical`
- `important`
- `minor`

The goal is to make missing coverage easy to inspect without hidden AI scoring.

## Readiness Recommendation

The response includes a plain-language recommendation such as:

- `Ready to apply`
- `Apply with caution`
- `Large evidence gaps`

This is intended for review workflows and candidate decision support, not hiring automation.

## Explicit Non-Goals

This feature does not do:

- hiring probability estimation;
- recruiter simulation;
- hidden ranking;
- LLM scoring;
- any other opaque AI judgment.

The output is meant to stay transparent, inspectable, and operational.
