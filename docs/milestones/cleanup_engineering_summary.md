# Cleanup Engineering Milestone: Resume / Cover Letter / Interview Safety

## Scope
- Refactored legacy candidate-specific bias handling into `LegacyResumeRecoveryService`
- Cleaned up `ProfileStructuringService`, `AchievementExtractionService`, `ResumeGenerationService`, `CoverLetterGenerationService`
- Updated interview prep fallback behavior to avoid inventing backend ownership claims
- Added targeted regression tests for legacy noise detection, neutral domain phrasing, and safe ownership language

## Key changes
1. Moved private resume noise heuristics into `LegacyResumeRecoveryService`
2. Delegated legacy layout/noise handling from profile and resume services to legacy recovery adapter
3. Removed hardcoded domain-specific phrases from resume/project synthesis
4. Neutralized `PROJECT_DISPLAY_HINTS` and cover-letter project context logic
5. Replaced invented ownership claims in interview fallback action with safe, evidence-based phrasing
6. Added guard tests to prevent future drift back into private-domain or overclaiming language

## Result
- Test run: `pytest tests/test_resume_generation_service.py tests/test_legacy_resume_recovery_service.py tests/test_cover_letter_generation_service.py tests/test_interview_answer_synthesis_service.py -q`
- Passed: `782 passed`

## Suggested commit/PR summary
**Title:** Cleanup legacy resume/cover-letter/interview synthesis paths and enforce neutral evidence language

**Description:**
- Centralized legacy noise handling in `LegacyResumeRecoveryService`
- Removed private candidate bias from core profile/resume/cover-letter services
- Replaced hardcoded domain-specific wording with neutral, generic project labels
- Hardened interview fallback wording to avoid invented backend ownership claims
- Added regression tests for legacy noise, disable flags, and neutral phrasing

## Milestone
- `cleanup_engineering_summary` complete
- Preserve engineering intent: keep legacy regression handling separate from core domain-neutral synthesis
- Next practical step: create PR with this summary and document the branch review notes here if needed
