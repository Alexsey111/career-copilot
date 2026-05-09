from __future__ import annotations

from app.domain.document_models import MatchKeywordSet, SelectedAchievement


def achievement_to_dict(
    achievement: SelectedAchievement,
) -> dict:
    payload = {
        "title": achievement.title,
        "situation": achievement.situation,
        "task": achievement.task,
        "action": achievement.action,
        "result": achievement.result,
        "metric_text": achievement.metric_text,
        "fact_status": achievement.fact_status,
        "reason": achievement.reason,
    }
    if achievement.id is not None:
        payload["id"] = achievement.id
    return payload


def ensure_selected_achievement(
    value: SelectedAchievement | dict,
) -> SelectedAchievement:
    if isinstance(value, SelectedAchievement):
        return value
    return SelectedAchievement(
        id=value.get("id"),
        title=value["title"],
        situation=value.get("situation"),
        task=value.get("task"),
        action=value.get("action"),
        result=value.get("result"),
        metric_text=value.get("metric_text"),
        fact_status=value["fact_status"],
        reason=value["reason"],
    )


def ensure_keyword_set(
    value: MatchKeywordSet | tuple[list[str], list[str]],
) -> MatchKeywordSet:
    if isinstance(value, MatchKeywordSet):
        return value
    matched, missing = value
    return MatchKeywordSet(
        matched=matched,
        missing=missing,
    )
