"""Demo scenario identifiers used by diagnostics, walkthroughs and local reset flows."""

from __future__ import annotations

from typing import Any


DEMO_SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "code": "scenario_a_ready_application",
        "label": "Scenario A — Ready application",
        "description": "A clean application with approved documents and no blockers.",
    },
    {
        "code": "scenario_b_unsupported_claims",
        "label": "Scenario B — Unsupported claims",
        "description": "A cover letter or document draft that still requires claim confirmation.",
    },
    {
        "code": "scenario_c_interview_gap_risk",
        "label": "Scenario C — Interview gap-risk",
        "description": "Interview prep output with gap-risk questions and careful-answer semantics.",
    },
    {
        "code": "scenario_d_low_confidence_evidence",
        "label": "Scenario D — Low confidence evidence",
        "description": "Evidence or provenance that needs review before it is treated as stable.",
    },
)


def get_demo_scenarios() -> list[dict[str, Any]]:
    return [dict(item) for item in DEMO_SCENARIOS]
