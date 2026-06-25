# Product Invariants

This document captures the product-level behaviors that must stay stable across document generation, review, resume/cover letter drafting, and interview prep.

These invariants are protected by automated tests, especially:

- `tests/test_e2e_multi_domain_regression.py`
- `tests/test_e2e_generalization_invariants.py`
- `tests/test_interview_prep_contract_snapshot.py`
- `tests/test_api_contract_snapshots.py`
- `tests/test_interview_prep_service.py`

## Invariants

1. Domain Requirement never becomes a Technical Skill.

2. Domain Requirement never becomes a Technical Question.

3. Strong claims must either be supported by evidence or marked as requiring review.

4. Every generated document requires human review before it is treated as final.

5. Cover Letter does not carry domain vocabulary from a different profession.

6. Interview Readiness always contains `explanation`.

7. Competency Coverage Matrix always exists in readiness payloads.

8. The algorithm must work correctly for both business domains and technology roles.

## Notes

- These invariants are intentionally cross-domain: legal, accounting, plumbing, design, backend, and similar roles should all behave consistently.
- If a new test reveals a regression, update the implementation first and then extend this document only when the invariant is truly part of the intended product contract.
- If a behavior is specific to one workflow, keep it in the workflow contract instead of broadening this document unnecessarily.
