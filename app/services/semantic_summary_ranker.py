# app\services\semantic_summary_ranker.py

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from app.services.evidence_strength_ranker import EvidenceStrengthRanker


@dataclass(slots=True)
class RankedSemanticItem:
    text: str
    score: int
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticSummaryRanker:
    """Ranks candidate-facing facts for concise document narratives."""

    def __init__(
        self,
        *,
        evidence_strength_ranker: EvidenceStrengthRanker | None = None,
    ) -> None:
        self.evidence_strength_ranker = (
            evidence_strength_ranker or EvidenceStrengthRanker()
        )

    def rank_focus_phrases(
        self,
        *,
        phrases: list[str],
        vacancy_title: str = "",
        selected_skills: list[str] | None = None,
        selected_achievements: list[dict[str, Any]] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
        source: str = "responsibility",
    ) -> list[str]:
        ranked = self.rank_items(
            phrases=phrases,
            vacancy_title=vacancy_title,
            selected_skills=selected_skills or [],
            selected_achievements=selected_achievements or [],
            top_alignment_evidence=top_alignment_evidence or [],
            source=source,
        )
        return [item.text for item in ranked]

    def rank_skills(
        self,
        *,
        skills: list[str],
        vacancy_title: str = "",
        selected_achievements: list[dict[str, Any]] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        return self.rank_focus_phrases(
            phrases=skills,
            vacancy_title=vacancy_title,
            selected_skills=skills,
            selected_achievements=selected_achievements or [],
            top_alignment_evidence=top_alignment_evidence or [],
            source="skill",
        )

    def rank_top_alignment_evidence(
        self,
        *,
        evidence_items: list[dict[str, Any]],
        vacancy_title: str = "",
        selected_skills: list[str] | None = None,
        selected_achievements: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        phrases = [
            str(item.get("summary_phrase") or "").strip()
            for item in evidence_items
            if str(item.get("summary_phrase") or "").strip()
        ]
        ranked = self.rank_items(
            phrases=phrases,
            vacancy_title=vacancy_title,
            selected_skills=selected_skills or [],
            selected_achievements=selected_achievements or [],
            top_alignment_evidence=evidence_items,
            source="top_alignment_evidence",
        )
        by_phrase = {
            str(item.get("summary_phrase") or "").strip(): item
            for item in evidence_items
            if str(item.get("summary_phrase") or "").strip()
        }
        return [
            by_phrase[item.text]
            for item in ranked
            if item.text in by_phrase
        ]

    def rank_items(
        self,
        *,
        phrases: list[str],
        vacancy_title: str = "",
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
        top_alignment_evidence: list[dict[str, Any]],
        source: str,
    ) -> list[RankedSemanticItem]:
        cleaned = self._dedupe_preserve_order(
            [str(value or "").strip() for value in phrases if str(value or "").strip()]
        )
        if not cleaned:
            return []

        context = self._ranking_context(
            vacancy_title=vacancy_title,
            selected_skills=selected_skills,
            selected_achievements=selected_achievements,
            top_alignment_evidence=top_alignment_evidence,
        )
        evidence_by_phrase = {
            str(item.get("summary_phrase") or "").strip(): item
            for item in top_alignment_evidence
            if str(item.get("summary_phrase") or "").strip()
        }

        ranked = [
            RankedSemanticItem(
                text=phrase,
                score=self.score_phrase(
                    phrase,
                    context=context,
                    source=source,
                    evidence_item=evidence_by_phrase.get(phrase),
                ),
                source=source,
                metadata=evidence_by_phrase.get(phrase, {}),
            )
            for phrase in cleaned
        ]
        ranked.sort(key=lambda item: (-item.score, cleaned.index(item.text)))
        return ranked

    def score_phrase(
        self,
        phrase: str,
        *,
        context: str,
        source: str = "responsibility",
        evidence_item: dict[str, Any] | None = None,
    ) -> int:
        text = str(phrase or "").casefold()
        score = 0

        weighted_markers = (
            (r"управлен|проект", 8),
            (r"координац|команд", 6),
            (r"срок|бюджет|планирован|контрол", 6),
            (r"заказчик|stakeholder|переговор", 5),
            (r"диагност|лечени|пациент", 6),
            (r"медицинск|документац", 4),
            (r"agile|scrum|kanban|jira|confluence", 4),
            (r"документац|отчет|отчёт", 2),
        )
        for pattern, weight in weighted_markers:
            if re.search(pattern, text):
                score += weight

        if source == "top_alignment_evidence":
            score += 5
        elif source == "skill":
            score += 2

        if evidence_item:
            confidence = str(evidence_item.get("confidence") or "").strip().lower()
            if confidence == "high":
                score += 5
            elif confidence == "medium":
                score += 3

        if re.search(r"руковод|project manager|проект", context):
            if re.search(r"управлен|проект|координац|срок|бюджет|заказчик", text):
                score += 4
        if re.search(r"терапевт|медицин|пациент", context):
            if re.search(r"диагност|лечени", text):
                score += 6
            if re.search(r"медицинск|документац", text):
                score += 4
            if re.search(r"координац", text):
                score -= 8

        if self._token_overlap_count(text, context):
            score += min(self._token_overlap_count(text, context), 4)
        if "%" in text or re.search(r"\b\d+\b", text):
            score += 2
        if len(text.split()) > 8:
            score -= 1
        return score

    def achievement_quality_score(self, achievement: dict[str, Any]) -> int:
        return self.evidence_strength_ranker.summary_quality_score(achievement)

    def strong_summary_achievements(
        self,
        selected_achievements: list[dict[str, Any]],
        *,
        min_score: int = 3,
        min_total_score: int = 25,
        vacancy_title: str = "",
        selected_skills: list[str] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        strong = [
            item
            for item in selected_achievements
            if self.achievement_quality_score(item) >= min_score
        ]
        return self.evidence_strength_ranker.rank_achievements(
            strong,
            vacancy_title=vacancy_title,
            selected_skills=selected_skills or [],
            top_alignment_evidence=top_alignment_evidence or [],
            min_score=min_total_score,
        )

    def looks_like_action_achievement(self, value: str) -> bool:
        return self.evidence_strength_ranker.looks_like_action_achievement(value)

    def _ranking_context(
        self,
        *,
        vacancy_title: str,
        selected_skills: list[str],
        selected_achievements: list[dict[str, Any]],
        top_alignment_evidence: list[dict[str, Any]],
    ) -> str:
        return " ".join(
            [
                str(vacancy_title or ""),
                " ".join(str(skill or "") for skill in selected_skills),
                " ".join(str(item.get("title") or "") for item in selected_achievements),
                " ".join(
                    " ".join(
                        str(item.get(field) or "")
                        for field in ("requirement", "evidence", "summary_phrase")
                    )
                    for item in top_alignment_evidence
                ),
            ]
        ).casefold()

    def _token_overlap_count(self, text: str, context: str) -> int:
        tokens = {
            token
            for token in re.findall(r"[a-zа-яё0-9]{3,}", text.casefold())
            if token not in {"для", "with", "and", "или", "при"}
        }
        context_tokens = set(re.findall(r"[a-zа-яё0-9]{3,}", context.casefold()))
        return len(tokens & context_tokens)

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = re.sub(r"\s+", " ", str(value or "").strip()).casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(str(value).strip())
        return result
