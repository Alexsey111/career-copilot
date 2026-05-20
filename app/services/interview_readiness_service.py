# app\services\interview_readiness_service.py

from __future__ import annotations

from typing import Any

from app.domain.interview_prep import (
    achievement_search_text,
    has_leadership_tokens,
    has_metric_text,
)


class InterviewReadinessService:
    def build_weak_areas(
        self,
        *,
        competency_map: dict[str, Any],
        confirmed_achievements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        weak_areas: list[dict[str, Any]] = []
        matched_skill_keys = self._matched_required_skill_keys(
            competency_map=competency_map,
            confirmed_achievements=confirmed_achievements,
        )

        for skill in competency_map.get("required_skills") or []:
            if skill["key"] in matched_skill_keys:
                continue

            weak_areas.append(
                {
                    "code": f"missing_confirmed_{skill['key']}",
                    "message": f"No confirmed {skill['label']} evidence",
                    "severity": "blocker",
                    "category": "technical",
                    "competency_key": skill["key"],
                    "evidence_count": 0,
                }
            )

        seniority = competency_map.get("seniority_expectations") or {}
        level = str(seniority.get("level") or "").lower()
        if level in {"senior", "lead", "staff", "principal"} and not self._has_leadership_evidence(
            confirmed_achievements
        ):
            weak_areas.append(
                {
                    "code": "missing_leadership_examples",
                    "message": "No leadership examples",
                    "severity": "blocker",
                    "category": "leadership",
                    "competency_key": "leadership",
                    "evidence_count": 0,
                }
            )

        if level in {"senior", "lead", "staff", "principal"} and not self._has_scale_metrics(
            confirmed_achievements
        ):
            weak_areas.append(
                {
                    "code": "missing_scale_metrics",
                    "message": "No scale metrics",
                    "severity": "warning",
                    "category": "metrics",
                    "competency_key": "scale_metrics",
                    "evidence_count": 0,
                }
            )

        if competency_map.get("domain_expectations") and not self._has_domain_evidence(
            confirmed_achievements,
            competency_map.get("domain_expectations") or [],
        ):
            weak_areas.append(
                {
                    "code": "missing_domain_context",
                    "message": "No confirmed domain-specific evidence",
                    "severity": "warning",
                    "category": "domain",
                    "competency_key": "domain_context",
                    "evidence_count": 0,
                }
            )

        return weak_areas

    def build_readiness(
        self,
        *,
        competency_map: dict[str, Any],
        weak_areas: list[dict[str, Any]],
        evidence_links: list[dict[str, Any]],
    ) -> dict[str, Any]:
        blockers = [
            item["message"]
            for item in weak_areas
            if str(item.get("severity") or "").lower() == "blocker"
        ]
        warnings = [
            item["message"]
            for item in weak_areas
            if str(item.get("severity") or "").lower() == "warning"
        ]

        required_skills = competency_map.get("required_skills") or []
        covered_required_skill_keys = {
            str(link.get("competency_key") or "")
            for link in evidence_links
            if str(link.get("question_category") or "") == "technical"
            and str(link.get("competency_key") or "")
        }
        covered_count = 0
        for skill in required_skills:
            if skill["key"] in covered_required_skill_keys:
                covered_count += 1

        required_count = len(required_skills) or 1
        coverage_ratio = covered_count / required_count

        score = round(coverage_ratio * 100)
        score -= len(blockers) * 20
        score -= len(warnings) * 8
        score = max(0, min(100, score))

        ready = not blockers and score >= 60
        return {
            "ready": ready,
            "blockers": blockers,
            "warnings": warnings,
            "score": score,
        }

    def _matched_required_skill_keys(
        self,
        *,
        competency_map: dict[str, Any],
        confirmed_achievements: list[dict[str, Any]],
    ) -> set[str]:
        matched: set[str] = set()
        for skill in competency_map.get("required_skills") or []:
            skill_text = str(skill["label"])
            skill_tokens = self._tokenize(skill_text)
            for achievement in confirmed_achievements:
                text = achievement_search_text(achievement)
                text_tokens = self._tokenize(text)
                if skill["key"] in text or skill_tokens & text_tokens:
                    matched.add(skill["key"])
                    break
        return matched

    def _has_leadership_evidence(self, achievements: list[dict[str, Any]]) -> bool:
        for achievement in achievements:
            if has_leadership_tokens(achievement_search_text(achievement)):
                return True
        return False

    def _has_scale_metrics(self, achievements: list[dict[str, Any]]) -> bool:
        for achievement in achievements:
            if has_metric_text(achievement):
                return True
        return False

    def _has_domain_evidence(
        self,
        achievements: list[dict[str, Any]],
        domain_expectations: list[str],
    ) -> bool:
        domain_text = " ".join(domain_expectations).lower()
        for achievement in achievements:
            text = achievement_search_text(achievement)
            if any(token in text for token in self._tokenize(domain_text)):
                return True
        return False

    def _tokenize(self, text: str) -> set[str]:
        import re

        return set(re.findall(r"[a-zа-я0-9]+", text.lower()))

