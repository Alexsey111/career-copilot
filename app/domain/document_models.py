# app\domain\document_models.py

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SelectedAchievement:
    id: str | None
    title: str
    situation: str | None
    task: str | None
    action: str | None
    result: str | None
    metric_text: str | None
    fact_status: str
    reason: str


@dataclass(slots=True)
class MatchKeywordSet:
    matched: list[str]
    missing: list[str]


@dataclass(slots=True)
class GapMitigation:
    keyword: str
    mitigation_text: str
