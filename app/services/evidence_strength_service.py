# app\services\evidence_strength_service.py

from __future__ import annotations

import re
from typing import Any, Mapping

from app.domain.evidence import (
    EvidenceFactStatus,
    EvidenceStrengthLevel,
    STAREvidenceSummary,
    build_star_summary,
    extract_skill_tags,
)


class EvidenceStrengthService:
    def calculate_strength_score(
        self,
        evidence: Mapping[str, Any],
        *,
        usage_count: int = 0,
    ) -> float:
        title = str(evidence.get("title") or "")
        snippet_text = str(evidence.get("snippet_text") or "")
        metric_text = str(evidence.get("metric_text") or "")
        evidence_note = str(evidence.get("evidence_note") or "")
        fact_status = str(evidence.get("fact_status") or "").strip().lower()
        star = self._resolve_star_summary(evidence)
        skills = evidence.get("skills") or extract_skill_tags(title, snippet_text, metric_text, evidence_note)

        score = 0.0

        if fact_status == EvidenceFactStatus.CONFIRMED:
            score += 0.35
        elif fact_status == EvidenceFactStatus.PARTIAL:
            score += 0.2

        if metric_text or self._has_numeric_signal(snippet_text, evidence_note, title):
            score += 0.25

        if evidence_note.strip():
            score += 0.1

        if star.is_complete:
            score += 0.2
        elif any([star.situation, star.task, star.action, star.result]):
            score += 0.1

        skill_count = len({str(skill).strip().lower() for skill in skills if str(skill).strip()})
        if skill_count >= 4:
            score += 0.15
        elif skill_count >= 2:
            score += 0.08

        if self._looks_vague(title, snippet_text):
            score -= 0.15

        score -= min(usage_count * 0.03, 0.15)

        return round(max(0.0, min(1.0, score)), 3)

    def classify_strength(self, score: float) -> EvidenceStrengthLevel:
        if score >= 0.7:
            return EvidenceStrengthLevel.STRONG
        if score >= 0.4:
            return EvidenceStrengthLevel.MEDIUM
        return EvidenceStrengthLevel.WEAK

    def explain_strength(
        self,
        evidence: Mapping[str, Any],
        *,
        usage_count: int = 0,
    ) -> dict[str, Any]:
        score = self.calculate_strength_score(evidence, usage_count=usage_count)
        star = self._resolve_star_summary(evidence)
        reasons: list[str] = []

        fact_status = str(evidence.get("fact_status") or "").strip().lower()
        if fact_status == EvidenceFactStatus.CONFIRMED:
            reasons.append("confirmed fact")
        elif fact_status == EvidenceFactStatus.PARTIAL:
            reasons.append("partial verification")
        else:
            reasons.append("unverified fact")

        if evidence.get("metric_text") or self._has_numeric_signal(
            str(evidence.get("snippet_text") or ""),
            str(evidence.get("evidence_note") or ""),
            str(evidence.get("title") or ""),
        ):
            reasons.append("has metric signal")

        if str(evidence.get("evidence_note") or "").strip():
            reasons.append("has evidence note")

        if star.is_complete:
            reasons.append("complete STAR")
        elif any([star.situation, star.task, star.action, star.result]):
            reasons.append("partial STAR")

        skills = evidence.get("skills") or []
        if skills:
            reasons.append(f"skills={len(skills)}")

        if usage_count:
            reasons.append(f"usage_penalty={usage_count}")

        return {
            "score": score,
            "strength": self.classify_strength(score).value,
            "reasons": reasons,
        }

    def _resolve_star_summary(self, evidence: Mapping[str, Any]) -> STAREvidenceSummary:
        star_value = evidence.get("star_summary")
        if isinstance(star_value, STAREvidenceSummary):
            return star_value
        if isinstance(star_value, dict):
            return STAREvidenceSummary(
                situation=str(star_value.get("situation") or "").strip() or None,
                task=str(star_value.get("task") or "").strip() or None,
                action=str(star_value.get("action") or "").strip() or None,
                result=str(star_value.get("result") or "").strip() or None,
            )
        return build_star_summary(evidence)

    def _has_numeric_signal(self, *texts: str) -> bool:
        combined = " ".join(texts).lower()
        if re.search(r"\b\d+(\.\d+)?\b", combined):
            return True
        numeric_keywords = [
            "%",
            "metric",
            "kpi",
            "latency",
            "throughput",
            "users",
            "requests",
            "revenue",
            "cost",
            "performance",
        ]
        return any(keyword in combined for keyword in numeric_keywords)

    def _looks_vague(self, title: str, snippet_text: str) -> bool:
        combined = f"{title} {snippet_text}".lower()
        vague_markers = [
            "helped",
            "participated",
            "worked on",
            "assisted",
            "contributed",
            "responsible for",
            "various tasks",
            "stuff",
        ]
        return any(marker in combined for marker in vague_markers)
