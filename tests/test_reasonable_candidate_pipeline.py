from __future__ import annotations

import pytest

from app.services.achievement_extraction_service import AchievementExtractionService
from app.services.profile_structuring_service import ProfileStructuringService
from fixtures.reasonable_candidates import REASONABLE_CANDIDATE_FIXTURES


@pytest.mark.parametrize(
    "fixture",
    REASONABLE_CANDIDATE_FIXTURES,
    ids=[fixture.kind for fixture in REASONABLE_CANDIDATE_FIXTURES],
)
def test_reasonable_candidate_inputs_do_not_break_pipeline(fixture) -> None:
    profile_service = ProfileStructuringService()
    achievement_service = AchievementExtractionService()

    draft = profile_service._build_draft(
        fixture.text,
        source_file_kind=fixture.source_file_kind,
    )
    achievement_drafts, warnings = achievement_service._build_achievement_drafts(
        fixture.text
    )

    assert draft is not None
    assert isinstance(draft.warnings, list)
    assert isinstance(warnings, list)

    for signal in draft.contribution_signals:
        assert signal.source_layer == "normalized_contribution_signal"
        assert signal.ownership_confidence in {"low", "medium", "high"}
        assert isinstance(signal.requires_confirmation, bool)

    for achievement in achievement_drafts:
        assert achievement.ownership_confidence == "low"
        assert achievement.requires_confirmation is True
        assert achievement.fact_status == "needs_confirmation"
