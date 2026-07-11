# app\services\evidence_strength_ranker.py

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass(slots=True)
class EvidenceStrengthScore:
    total: int
    vacancy_relevance: int
    evidence_strength: int
    ats_keywords: int
    diversity: int
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RankedAchievement:
    achievement: dict[str, Any]
    score: EvidenceStrengthScore


class EvidenceStrengthRanker:
    """Scores achievements by persuasiveness, not just topical relevance."""

    def rank_achievements(
        self,
        achievements: list[dict[str, Any]],
        *,
        vacancy_title: str = "",
        selected_skills: list[str] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
        min_score: int = 0,
    ) -> list[dict[str, Any]]:
        ranked = self.rank_achievement_items(
            achievements,
            vacancy_title=vacancy_title,
            selected_skills=selected_skills or [],
            top_alignment_evidence=top_alignment_evidence or [],
        )
        return [
            item.achievement
            for item in ranked
            if item.score.total >= min_score
        ]

    def rank_achievement_items(
        self,
        achievements: list[dict[str, Any]],
        *,
        vacancy_title: str = "",
        selected_skills: list[str] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
    ) -> list[RankedAchievement]:
        context = self._context(
            vacancy_title=vacancy_title,
            selected_skills=selected_skills or [],
            top_alignment_evidence=top_alignment_evidence or [],
        )
        ranked: list[RankedAchievement] = []
        seen_signatures: set[str] = set()

        for achievement in achievements:
            score = self.score_achievement(
                achievement,
                context=context,
                selected_skills=selected_skills or [],
                top_alignment_evidence=top_alignment_evidence or [],
                seen_signatures=seen_signatures,
            )
            ranked.append(RankedAchievement(achievement=achievement, score=score))
            signature = self._diversity_signature(achievement)
            if signature:
                seen_signatures.add(signature)

        ranked.sort(
            key=lambda item: (
                -item.score.total,
                -item.score.evidence_strength,
                achievements.index(item.achievement),
            )
        )
        return ranked

    def score_achievement(
        self,
        achievement: dict[str, Any],
        *,
        context: str = "",
        selected_skills: list[str] | None = None,
        top_alignment_evidence: list[dict[str, Any]] | None = None,
        seen_signatures: set[str] | None = None,
    ) -> EvidenceStrengthScore:
        evidence_strength, evidence_reasons = self._evidence_strength_component(
            achievement
        )
        vacancy_relevance, relevance_reasons = self._vacancy_relevance_component(
            achievement,
            context=context,
            top_alignment_evidence=top_alignment_evidence or [],
        )
        ats_keywords, ats_reasons = self._ats_keyword_component(
            achievement,
            context=context,
            selected_skills=selected_skills or [],
        )
        diversity, diversity_reasons = self._diversity_component(
            achievement,
            seen_signatures=seen_signatures or set(),
        )

        total = vacancy_relevance + evidence_strength + ats_keywords + diversity
        return EvidenceStrengthScore(
            total=max(total, 0),
            vacancy_relevance=vacancy_relevance,
            evidence_strength=evidence_strength,
            ats_keywords=ats_keywords,
            diversity=diversity,
            reasons=[
                *relevance_reasons,
                *evidence_reasons,
                *ats_reasons,
                *diversity_reasons,
            ],
        )

    def summary_quality_score(self, achievement: dict[str, Any]) -> int:
        title = str(achievement.get("title") or "").strip()
        action = str(achievement.get("action") or "").strip()
        result = str(achievement.get("result") or "").strip()
        metric = str(achievement.get("metric_text") or "").strip()

        score = 0
        if action or self.looks_like_action_achievement(title):
            score += 1
        if result or self._has_result_signal(title):
            score += 1
        if metric or self._has_metric_signal(title):
            score += 2
        return score

    def looks_like_action_achievement(self, value: str) -> bool:
        return bool(
            re.match(
                r"^\s*(запустил|запустила|снизил|снизила|внедрил|внедрила|"
                r"сократил|сократила|оптимизировал|оптимизировала|"
                r"подготовил|подготовила|пров[её]л|провела|разработал|разработала|"
                r"создал|создала|автоматизировал|автоматизировала|built|launched|"
                r"reduced|implemented|improved|optimized|delivered)\b",
                str(value or ""),
                flags=re.IGNORECASE,
            )
        )

    def _evidence_strength_component(
        self,
        achievement: dict[str, Any],
    ) -> tuple[int, list[str]]:
        title = str(achievement.get("title") or "").strip()
        action = str(achievement.get("action") or "").strip()
        result = str(achievement.get("result") or "").strip()
        metric = str(achievement.get("metric_text") or "").strip()
        fact_status = str(achievement.get("fact_status") or "").strip().lower()
        ownership = str(
            achievement.get("ownership_confidence")
            or achievement.get("candidate_ownership_confidence")
            or ""
        ).strip().lower()

        score = 0
        reasons: list[str] = []
        if action or self.looks_like_action_achievement(title):
            score += 8
            reasons.append("action")
        if result or self._has_result_signal(title):
            score += 8
            reasons.append("result")
        if metric or self._has_metric_signal(title):
            score += 10
            reasons.append("metric")
        if fact_status in {"confirmed", "user_provided"}:
            score += 4
            reasons.append("confirmed")
        elif fact_status in {"needs_confirmation", "partial", "pending"}:
            score += 1
            reasons.append("needs_confirmation")
        if ownership in {"low", "unknown", "needs_review"}:
            score -= 5
            reasons.append("low_ownership")

        return max(min(score, 30), 0), reasons

    def _vacancy_relevance_component(
        self,
        achievement: dict[str, Any],
        *,
        context: str,
        top_alignment_evidence: list[dict[str, Any]],
    ) -> tuple[int, list[str]]:
        text = self._achievement_text(achievement)
        score = min(self._token_overlap_count(text, context) * 4, 18)
        reasons: list[str] = ["vacancy_overlap"] if score else []

        marker_score = 0
        if re.search(r"проект|project|scrum|agile|jira", context):
            if re.search(r"проект|срок|бюджет|команд|заказчик|stakeholder", text):
                marker_score += 12
        if re.search(r"automation|автоматизац|ai|ии|llm|workflow", context):
            if re.search(r"automation|автоматизац|ai|ии|llm|workflow|openai", text):
                marker_score += 12
        if re.search(r"юрист|legal|договор|претензи", context):
            if re.search(r"договор|претензи|судеб|legal", text):
                marker_score += 12
        if re.search(r"терапевт|медицин|пациент", context):
            if re.search(r"пациент|консультац|лечени|диагност", text):
                marker_score += 12
        if marker_score:
            reasons.append("domain_match")

        alignment_score = self._alignment_component(text, top_alignment_evidence)
        if alignment_score:
            reasons.append("top_alignment_evidence")

        return min(score + marker_score + alignment_score, 45), reasons

    def _ats_keyword_component(
        self,
        achievement: dict[str, Any],
        *,
        context: str,
        selected_skills: list[str],
    ) -> tuple[int, list[str]]:
        text = self._achievement_text(achievement)
        keyword_context = " ".join([context, *selected_skills])
        score = min(self._token_overlap_count(text, keyword_context) * 5, 15)
        return score, ["ats_keywords"] if score else []

    def _diversity_component(
        self,
        achievement: dict[str, Any],
        *,
        seen_signatures: set[str],
    ) -> tuple[int, list[str]]:
        signature = self._diversity_signature(achievement)
        if signature and signature in seen_signatures:
            return 2, ["duplicate_theme"]
        return 10, ["diverse"]

    def _alignment_component(
        self,
        text: str,
        top_alignment_evidence: list[dict[str, Any]],
    ) -> int:
        score = 0
        for item in top_alignment_evidence:
            alignment_text = " ".join(
                str(item.get(field) or "")
                for field in ("requirement", "evidence", "summary_phrase")
            )
            overlap = self._token_overlap_count(text, alignment_text)
            if not overlap:
                continue
            confidence = str(item.get("confidence") or "").strip().lower()
            if confidence == "high":
                score += 10
            elif confidence == "medium":
                score += 6
            else:
                score += 3
        return min(score, 15)

    def _achievement_text(self, achievement: dict[str, Any]) -> str:
        return " ".join(
            str(achievement.get(field) or "")
            for field in (
                "title",
                "situation",
                "task",
                "action",
                "result",
                "metric_text",
                "reason",
                "evidence_note",
            )
        ).casefold()

    def _context(
        self,
        *,
        vacancy_title: str,
        selected_skills: list[str],
        top_alignment_evidence: list[dict[str, Any]],
    ) -> str:
        return " ".join(
            [
                str(vacancy_title or ""),
                " ".join(str(skill or "") for skill in selected_skills),
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
        tokens = self._tokens(text)
        context_tokens = self._tokens(context)
        return len(tokens & context_tokens)

    def _tokens(self, value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zа-яё0-9]{3,}", str(value or "").casefold())
            if token not in {"для", "with", "and", "или", "при", "the"}
        }

    def _has_metric_signal(self, value: str) -> bool:
        return bool(
            "%" in str(value or "")
            or re.search(r"\b\d+\b", str(value or ""))
            or re.search(r"\b(более|до|на|times|percent)\b", str(value or ""), re.IGNORECASE)
        )

    def _has_result_signal(self, value: str) -> bool:
        return bool(
            re.search(
                r"\b(снизил|снизила|сократил|сократила|увеличил|увеличила|"
                r"улучшил|улучшила|оптимизировал|оптимизировала|запустил|запустила|"
                r"reduced|increased|improved|optimized|delivered|launched)\b",
                str(value or ""),
                flags=re.IGNORECASE,
            )
        )

    def _diversity_signature(self, achievement: dict[str, Any]) -> str:
        text = self._achievement_text(achievement)
        tokens = sorted(
            token
            for token in self._tokens(text)
            if not re.fullmatch(r"\d+", token)
        )
        return " ".join(tokens[:4])
