# app\services\interview_readiness_service.py

from __future__ import annotations

import re
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
        evidence_snippets: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        weak_areas: list[dict[str, Any]] = []
        matched_skill_keys = self._matched_required_skill_keys(
            competency_map=competency_map,
            confirmed_achievements=confirmed_achievements,
            evidence_snippets=evidence_snippets or [],
        )

        for skill in competency_map.get("required_skills") or []:
            if skill["key"] in matched_skill_keys:
                continue

            has_partial = self._has_partial_skill_evidence(
                skill_key=skill["key"],
                skill_label=skill["label"],
                evidence_snippets=evidence_snippets or [],
            )
            message = f"No confirmed {skill['label']} evidence"
            if has_partial:
                message += ". GitHub/resume evidence exists but still requires confirmation."

            weak_areas.append(
                {
                    "code": f"missing_confirmed_{skill['key']}",
                    "message": message,
                    "severity": "blocker",
                    "category": "technical",
                    "competency_key": skill["key"],
                    "evidence_count": 0,
                }
            )

        seniority = competency_map.get("seniority_expectations") or {}
        level = str(seniority.get("level") or "").lower()
        evidence_snippets = evidence_snippets or []
        if level in {"senior", "lead", "staff", "principal"} and not self._has_leadership_evidence(
            confirmed_achievements,
            evidence_snippets,
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
            confirmed_achievements,
            evidence_snippets,
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
            evidence_snippets,
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
        evidence_snippets: list[dict[str, Any]],
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
            if skill["key"] in matched:
                continue
            for evidence in evidence_snippets:
                if not self._is_interview_ready_evidence(evidence):
                    continue
                text = self._evidence_search_text(evidence)
                text_tokens = self._tokenize(text)
                evidence_skills = {
                    str(item).strip().lower().replace(" ", "_")
                    for item in (evidence.get("skills") or [])
                    if str(item).strip()
                }
                if (
                    skill["key"] in text
                    or skill["key"] in evidence_skills
                    or skill_tokens & text_tokens
                    or skill_tokens & self._tokenize(" ".join(evidence_skills))
                ):
                    matched.add(skill["key"])
                    break
        return matched

    def _has_leadership_evidence(
        self,
        achievements: list[dict[str, Any]],
        evidence_snippets: list[dict[str, Any]],
    ) -> bool:
        for achievement in achievements:
            if has_leadership_tokens(achievement_search_text(achievement)):
                return True
        for evidence in evidence_snippets:
            if self._is_interview_ready_evidence(evidence) and has_leadership_tokens(
                self._evidence_search_text(evidence)
            ):
                return True
        return False

    def _has_scale_metrics(
        self,
        achievements: list[dict[str, Any]],
        evidence_snippets: list[dict[str, Any]],
    ) -> bool:
        for achievement in achievements:
            if has_metric_text(achievement):
                return True
        for evidence in evidence_snippets:
            if self._is_interview_ready_evidence(evidence) and self._has_metric_signal(evidence):
                return True
        return False

    def _has_domain_evidence(
        self,
        achievements: list[dict[str, Any]],
        evidence_snippets: list[dict[str, Any]],
        domain_expectations: list[str],
    ) -> bool:
        domain_text = " ".join(domain_expectations).lower()
        for achievement in achievements:
            text = achievement_search_text(achievement)
            if any(token in text for token in self._tokenize(domain_text)):
                return True
        for evidence in evidence_snippets:
            if not self._is_interview_ready_evidence(evidence):
                continue
            text = self._evidence_search_text(evidence)
            if any(token in text for token in self._tokenize(domain_text)):
                return True
        return False

    def _is_interview_ready_evidence(self, evidence: dict[str, Any]) -> bool:
        return str(evidence.get("fact_status") or "").strip().lower() in {
            "confirmed",
            "user_provided",
        }

    def _has_partial_skill_evidence(
        self,
        *,
        skill_key: str,
        skill_label: str,
        evidence_snippets: list[dict[str, Any]],
    ) -> bool:
        skill_tokens = self._tokenize(skill_label)

        for evidence in evidence_snippets:
            fact_status = str(
                evidence.get("fact_status") or ""
            ).strip().lower()

            if fact_status not in {
                "needs_confirmation",
                "partial",
            }:
                continue

            text = self._evidence_search_text(evidence)
            text_tokens = self._tokenize(text)

            evidence_skills = {
                str(item).strip().lower().replace(" ", "_")
                for item in (evidence.get("skills") or [])
                if str(item).strip()
            }

            if (
                skill_key in text
                or skill_key in evidence_skills
                or skill_tokens & text_tokens
            ):
                return True

        return False

    def _evidence_search_text(self, evidence: dict[str, Any]) -> str:
        star_summary = evidence.get("star_summary") or {}
        return " ".join(
            str(value or "")
            for value in [
                evidence.get("title"),
                evidence.get("snippet_text"),
                evidence.get("evidence_note"),
                " ".join(str(skill) for skill in (evidence.get("skills") or [])),
                star_summary.get("situation"),
                star_summary.get("task"),
                star_summary.get("action"),
                star_summary.get("result"),
            ]
        ).lower()

    def _has_metric_signal(self, evidence: dict[str, Any]) -> bool:
        text = self._evidence_search_text(evidence)
        return bool(
            re.search(r"\b\d+(\.\d+)?\b", text)
            or any(
                keyword in text
                for keyword in [
                    "%",
                    "latency",
                    "throughput",
                    "requests per second",
                    "rps",
                    "users",
                    "scale",
                    "performance",
                ]
            )
        )

    def _tokenize(self, text: str) -> set[str]:
        import re

        return set(re.findall(r"[a-zа-я0-9]+", text.lower()))
