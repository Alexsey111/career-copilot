# app/services/achievement_retrieval_service.py

from __future__ import annotations

import re
from typing import Any

from app.domain.document_models import SelectedAchievement
from app.domain.trace_models import GenerationTrace


class AchievementRetrievalService:
    """Сервис для выбора достижений, релевантных требованиям вакансии."""

    SCORE_THRESHOLD = 30

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def score_achievement_against_requirement(
        self,
        achievement: dict[str, Any],
        requirement_text: str | None,
    ) -> int:
        """Оценивает, насколько achievement соответствует одному требованию."""
        if not requirement_text:
            return 0

        requirement_tokens = set(self._tokenize(requirement_text))
        if not requirement_tokens:
            return 0

        achievement_text = " ".join(
            str(achievement.get(field) or "")
            for field in [
                "title",
                "situation",
                "task",
                "action",
                "result",
                "metric_text",
            ]
        )
        achievement_tokens = set(self._tokenize(achievement_text))
        if not achievement_tokens:
            return 0

        matches = requirement_tokens & achievement_tokens
        if not matches:
            return 0

        score = len(matches) / len(requirement_tokens)
        return min(100, int(round(score * 100)))

    def select_relevant_achievements(
        self,
        achievements: list[dict[str, Any]],
        requirements: list[dict[str, Any]],
        max_results: int = 3,
    ) -> tuple[list[SelectedAchievement], GenerationTrace]:
        """Возвращает подтверждённые достижения, релевантные требованиям вакансии."""
        selected: list[SelectedAchievement] = []
        trace_entries: list[dict[str, Any]] = []

        requirement_candidates = [
            req for req in requirements if req.get("text")
        ]

        for achievement in achievements:
            fact_status = str(achievement.get("fact_status") or "needs_confirmation")
            evidence_note = (achievement.get("evidence_note") or "").strip()
            title = str(achievement.get("title") or "").strip()

            if fact_status != "confirmed":
                continue
            if not evidence_note:
                continue
            if not title:
                continue
            if not requirement_candidates:
                continue

            best_score = 0
            best_requirement_text = None
            best_scope = None
            best_matches: list[str] = []

            for requirement in requirement_candidates:
                score = self.score_achievement_against_requirement(
                    achievement=achievement,
                    requirement_text=str(requirement.get("text") or ""),
                )
                if score <= best_score:
                    continue

                tokens = self._tokenize(requirement.get("text") or "")
                matched = sorted(set(tokens) & set(self._tokenize(title)))
                best_score = score
                best_requirement_text = requirement.get("text")
                best_scope = requirement.get("scope") or "must_have"
                best_matches = matched

            if best_score < self.SCORE_THRESHOLD:
                continue

            reason = (
                "must_have_match"
                if best_scope == "must_have"
                else "nice_to_have_match"
            )

            selected.append(SelectedAchievement(
                id=achievement.get("id"),
                title=title,
                situation=achievement.get("situation"),
                task=achievement.get("task"),
                action=achievement.get("action"),
                result=achievement.get("result"),
                metric_text=achievement.get("metric_text"),
                fact_status="confirmed",
                reason=reason,
            ))

            trace_entries.append({
                "achievement_id": achievement.get("id"),
                "requirement_text": best_requirement_text,
                "scope": best_scope,
                "score": best_score,
                "matched_keywords": best_matches,
                "why_selected": (
                    f"Achievement подтверждён и соответствует требованию: "
                    f"'{best_requirement_text}'."
                ),
                "evidence_note": evidence_note,
            })

        trace = GenerationTrace(
            selected_achievement_ids=[
                item.id for item in selected if item.id
            ],
            matched_keywords=[
                keyword
                for entry in trace_entries
                for keyword in entry.get("matched_keywords", [])
            ],
            retrieval_trace=trace_entries,
        )

        return selected[:max_results], trace
