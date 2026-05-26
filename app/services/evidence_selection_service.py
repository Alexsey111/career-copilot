# D:\python projects\career-copilot\app\services\evidence_selection_service.py

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from app.domain.evidence import (
    EvidenceSnippet,
    EvidenceStrengthLevel,
    dedupe_preserve_order,
    extract_skill_tags,
)


class EvidenceSelectionService:
    def rank_evidence(
        self,
        *,
        query_text: str,
        evidence_items: Sequence[EvidenceSnippet | Mapping[str, Any]],
        required_skills: Sequence[str] | None = None,
        source_types: Sequence[str] | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        query_skills = set(extract_skill_tags(query_text, " ".join(required_skills or [])))
        required_skill_tags = {
            item.strip().lower().replace(" ", "_")
            for item in (required_skills or [])
            if str(item).strip()
        }
        allowed_sources = {
            str(item).strip().lower()
            for item in (source_types or [])
            if str(item).strip()
        }

        ranked: list[dict[str, Any]] = []
        for item in evidence_items:
            snippet = self._coerce_snippet(item)
            snippet_source = str(snippet.get("source_type") or "").strip().lower()
            if allowed_sources and snippet_source not in allowed_sources:
                continue

            skills = {
                str(skill).strip().lower().replace(" ", "_")
                for skill in (snippet.get("skills") or [])
                if str(skill).strip()
            }
            overlap = query_skills & skills
            required_overlap = required_skill_tags & skills

            if not overlap and not required_overlap and query_skills:
                continue

            strength_bonus = self._strength_bonus(str(snippet.get("evidence_strength") or ""))
            fact_bonus = self._fact_status_bonus(str(snippet.get("fact_status") or ""))
            usage_penalty = self._usage_penalty(snippet)
            star_bonus = self._star_bonus(snippet)
            source_bonus = self._source_bonus(query_text, snippet_source)
            score = (
                len(overlap) * 0.25
                + len(required_overlap) * 0.2
                + strength_bonus
                + fact_bonus
                + star_bonus
                + source_bonus
                - usage_penalty
            )

            ranked.append(
                {
                    "evidence_id": snippet.get("id"),
                    "title": snippet.get("title"),
                    "snippet_text": snippet.get("snippet_text"),
                    "source_type": snippet_source,
                    "skills": list(snippet.get("skills") or []),
                    "evidence_strength": snippet.get("evidence_strength"),
                    "fact_status": snippet.get("fact_status"),
                    "usage_count": snippet.get("usage_count", 0),
                    "used_in_documents_count": snippet.get("used_in_documents_count", 0),
                    "used_in_interviews_count": snippet.get("used_in_interviews_count", 0),
                    "score": round(max(0.0, score), 3),
                    "reason": self._build_reason(
                        overlap=overlap,
                        required_overlap=required_overlap,
                        snippet=snippet,
                        strength_bonus=strength_bonus,
                        fact_bonus=fact_bonus,
                        usage_penalty=usage_penalty,
                        star_bonus=star_bonus,
                        source_bonus=source_bonus,
                    ),
                }
            )

        ranked.sort(
            key=lambda item: (
                item["score"],
                int(item.get("usage_count") or 0) * -1,
            ),
            reverse=True,
        )
        return ranked[:limit]

    def select_top_evidence(
        self,
        *,
        query_text: str,
        evidence_items: Sequence[EvidenceSnippet | Mapping[str, Any]],
        required_skills: Sequence[str] | None = None,
        source_types: Sequence[str] | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        return self.rank_evidence(
            query_text=query_text,
            evidence_items=evidence_items,
            required_skills=required_skills,
            source_types=source_types,
            limit=limit,
        )

    def _coerce_snippet(self, item: EvidenceSnippet | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(item, EvidenceSnippet):
            return item.as_dict()
        return dict(item)

    def _strength_bonus(self, value: str) -> float:
        normalized = value.strip().lower()
        if normalized == EvidenceStrengthLevel.STRONG:
            return 0.45
        if normalized == EvidenceStrengthLevel.MEDIUM:
            return 0.25
        return 0.1

    def _fact_status_bonus(self, value: str) -> float:
        normalized = value.strip().lower()
        if normalized == "confirmed":
            return 0.35
        if normalized == "user_provided":
            return 0.22
        if normalized in {"partial", "needs_confirmation", "pending"}:
            return 0.12
        return -0.35

    def _usage_penalty(self, snippet: Mapping[str, Any]) -> float:
        usage_count = int(snippet.get("usage_count") or 0)
        documents_count = int(snippet.get("used_in_documents_count") or 0)
        interviews_count = int(snippet.get("used_in_interviews_count") or 0)
        return min(0.06 * usage_count + 0.08 * documents_count + 0.08 * interviews_count, 0.6)

    def _is_complete_star(self, snippet: Mapping[str, Any]) -> bool:
        star_summary = snippet.get("star_summary") or {}
        return all(
            str(star_summary.get(field) or "").strip()
            for field in ("situation", "task", "action", "result")
        )

    def _star_bonus(self, snippet: Mapping[str, Any]) -> float:
        star_summary = snippet.get("star_summary") or {}
        values = [str(star_summary.get(field) or "").strip() for field in ("situation", "task", "action", "result")]
        filled = sum(1 for value in values if value)
        if filled == 4:
            return 0.2
        if filled >= 2:
            return 0.08
        return -0.08

    def _source_bonus(self, query_text: str, source_type: str) -> float:
        normalized_query = query_text.lower()
        if "interview" in normalized_query and source_type == "interview":
            return 0.15
        if "resume" in normalized_query and source_type in {"achievement", "resume", "resume_structured"}:
            return 0.1
        if "recommend" in normalized_query and source_type in {"manual", "achievement"}:
            return 0.08
        return 0.0

    def _build_reason(
        self,
        *,
        overlap: set[str],
        required_overlap: set[str],
        snippet: Mapping[str, Any],
        strength_bonus: float,
        fact_bonus: float,
        usage_penalty: float,
        star_bonus: float,
        source_bonus: float,
    ) -> str:
        parts: list[str] = []
        if overlap:
            parts.append(f"{len(overlap)} skill matches")
        if required_overlap:
            parts.append(f"{len(required_overlap)} required skill matches")
        if strength_bonus >= 0.45:
            parts.append("strong evidence")
        elif strength_bonus >= 0.25:
            parts.append("medium evidence")
        else:
            parts.append("weak evidence")
        if fact_bonus >= 0.3:
            parts.append("confirmed")
        elif fact_bonus >= 0.2:
            parts.append("user-provided")
        elif fact_bonus > 0:
            parts.append("partially verified")
        else:
            parts.append("unverified")
        if star_bonus > 0:
            parts.append("complete STAR")
        elif star_bonus < 0:
            parts.append("incomplete STAR")
        if source_bonus:
            parts.append("source boost")
        if usage_penalty:
            parts.append(f"usage penalty={usage_penalty:.2f}")
        skills = dedupe_preserve_order([str(skill) for skill in (snippet.get("skills") or [])])
        if skills:
            parts.append("skills=" + ", ".join(skills[:4]))
        return ", ".join(parts)
