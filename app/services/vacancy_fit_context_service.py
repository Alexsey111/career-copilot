# app\services\vacancy_fit_context_service.py

from __future__ import annotations

import re
from typing import Any

from app.domain.requirement_normalization import requirement_match_key
from app.domain.text_normalization import (
    humanize_vacancy_requirement_phrase,
    make_user_facing_evidence_phrase,
)
from app.services.vacancy_fit_narrative_service import VacancyFitNarrativeService


class VacancyFitContextService:
    def build(
        self,
        *,
        matched_keywords: list[str],
        missing_keywords: list[str],
        selected_skills: list[str],
        evidence_snippets: list[dict[str, Any]],
        selected_achievements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        vacancy_evidence_alignment = self._build_vacancy_evidence_alignment(
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            selected_skills=selected_skills,
            evidence_snippets=evidence_snippets,
            selected_achievements=selected_achievements,
        )
        vacancy_fit_narrative = VacancyFitNarrativeService().build(
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            vacancy_evidence_alignment=vacancy_evidence_alignment,
            selected_achievements=selected_achievements,
            selected_skills=selected_skills,
        )
        matched_labels = {
            requirement_match_key(str(item.get("label") or ""))
            for item in vacancy_fit_narrative.get("matched_strengths", [])
            if requirement_match_key(str(item.get("label") or ""))
        }
        vacancy_fit_narrative["critical_gaps"] = [
            item
            for item in vacancy_fit_narrative.get("critical_gaps", [])
            if requirement_match_key(str(item.get("label") or ""))
            not in matched_labels
        ]
        return {
            "vacancy_evidence_alignment": vacancy_evidence_alignment,
            "vacancy_fit_narrative": vacancy_fit_narrative,
        }

    def _build_vacancy_evidence_alignment(
        self,
        *,
        matched_keywords: list[str],
        missing_keywords: list[str],
        selected_skills: list[str],
        evidence_snippets: list[dict[str, Any]],
        selected_achievements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        requirements = self._dedupe_preserve_order(
            [
                self._display_relevance_label(str(item).strip())
                for item in [*matched_keywords, *missing_keywords]
                if str(item).strip()
            ]
        )
        selected_titles = {
            str(item.get("title") or "").strip().lower()
            for item in selected_achievements
            if str(item.get("title") or "").strip()
        }
        selected_skill_keys = {
            self._normalize_display_skill(skill).strip().lower()
            for skill in selected_skills
            if str(skill).strip()
        }

        alignment: list[dict[str, Any]] = []
        for requirement in requirements:
            evidence = self._find_best_evidence_for_competency(
                requirement,
                evidence_snippets,
            )
            evidence_title = (
                str(evidence.get("title") or "").strip().lower()
                if evidence
                else ""
            )
            requirement_title = str(requirement or "").strip().lower()
            if (
                evidence
                and selected_titles
                and evidence_title not in selected_titles
                and evidence_title != requirement_title
            ):
                evidence = None

            evidence_label = (
                self._render_alignment_evidence_label(evidence)
                if evidence
                else None
            )
            skill_supported = self._requirement_supported_by_skills(
                requirement=requirement,
                selected_skill_keys=selected_skill_keys,
            )
            label_is_fallback = False
            if evidence_label is None and skill_supported:
                evidence_label = humanize_vacancy_requirement_phrase(requirement)
                if evidence_label is None:
                    evidence_label = self._display_relevance_label(requirement)
                label_is_fallback = True

            confidence = (
                "high"
                if evidence_label and not label_is_fallback
                else "medium" if skill_supported else "gap"
            )
            alignment.append(
                {
                    "requirement": requirement,
                    "evidence": evidence_label,
                    "confidence": confidence,
                    "evidence_id": evidence.get("id") if evidence else None,
                    "fact_status": evidence.get("fact_status") if evidence else "needs_review",
                }
            )

        return self._dedupe_vacancy_evidence_alignment(alignment)[:8]

    def _find_best_evidence_for_competency(
        self,
        competency: str,
        evidence_snippets: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        competency_tokens = {
            token
            for token in re.split(r"[^a-z0-9а-яё]+", competency.lower())
            if len(token) >= 3
        }
        competency_markers = self._competency_specific_markers(competency)
        requires_direct_evidence = self._requires_direct_competency_evidence(
            competency
        )
        best: tuple[int, dict[str, Any]] | None = None
        fallback_best: tuple[int, dict[str, Any]] | None = None

        for snippet in evidence_snippets:
            text = " ".join(
                [
                    str(snippet.get("title") or ""),
                    str(snippet.get("snippet_text") or ""),
                    " ".join(str(skill) for skill in snippet.get("skills") or []),
                ]
            ).lower()
            score = sum(1 for token in competency_tokens if token in text)
            marker_score = sum(1 for marker in competency_markers if marker in text)
            if competency_markers and marker_score <= 0:
                if requires_direct_evidence:
                    continue
                if score > 0 and (
                    fallback_best is None or score > fallback_best[0]
                ):
                    fallback_best = (score, snippet)
                continue

            score += marker_score * 4
            score += self._category_competency_bonus(
                competency=competency,
                evidence=snippet,
            )
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, snippet)

        if best:
            return best[1]
        if requires_direct_evidence:
            return None
        return fallback_best[1] if fallback_best else None

    def _competency_specific_markers(self, competency: str) -> set[str]:
        normalized = competency.strip().lower().replace("_", " ")
        marker_map = {
            "git": {"git", "github", "version control", "repository"},
            "version control": {"git", "github", "version control", "repository"},
            "fastapi": {"fastapi", "api", "backend", "apirouter"},
            "backend": {"backend", "fastapi", "api", "persistence"},
            "docker": {"docker", "dockerfile", "docker-compose", "infrastructure"},
            "pytest": {"pytest", "tests", "testclient", "testing"},
            "testing": {"pytest", "tests", "testclient", "testing"},
            "postgresql": {"postgresql", "postgres", "sqlalchemy", "persistence"},
            "sqlalchemy": {"sqlalchemy", "postgresql", "persistence"},
            "workflow automation": {"workflow", "automation", "nocode", "no-code"},
        }
        for marker, values in marker_map.items():
            if marker in normalized:
                return values
        return set()

    def _requires_direct_competency_evidence(self, competency: str) -> bool:
        normalized = competency.strip().lower().replace("_", " ")
        return "git" in normalized or normalized in {
            "ai",
            "искусственный интеллект",
            "artificial intelligence",
        }

    def _category_competency_bonus(
        self,
        *,
        competency: str,
        evidence: dict[str, Any],
    ) -> int:
        normalized = competency.strip().lower()
        bucket = self._evidence_diversity_bucket(evidence)
        if any(marker in normalized for marker in ("fastapi", "backend", "api")):
            return 3 if bucket == "backend" else 0
        if any(marker in normalized for marker in ("docker", "infra")):
            return 3 if bucket == "backend" else 0
        if any(marker in normalized for marker in ("pytest", "testing", "test")):
            text = " ".join(
                [
                    str(evidence.get("title") or ""),
                    str(evidence.get("snippet_text") or ""),
                    " ".join(str(skill) for skill in evidence.get("skills") or []),
                ]
            ).lower()
            return 4 if any(marker in text for marker in ("pytest", "testing", "testclient")) else 0
        if "workflow" in normalized:
            return 3 if bucket in {"ai_workflow", "automation"} else 0
        return 0

    def _evidence_diversity_bucket(self, evidence: dict[str, Any]) -> str:
        category = self._achievement_category_from_evidence(evidence)
        if category in {"github_architecture", "backend_project", "architecture_evidence"}:
            return "backend"
        if category == "ai_workflow":
            return "ai_workflow"
        if category in {"automation_project", "automation", "prompt_engineering", "ai_project"}:
            return "automation"
        if category == "computer_vision":
            return "computer_vision"
        if category == "analytics_project":
            return "analytics"
        return "automation"

    def _achievement_category_from_evidence(self, evidence: dict[str, Any]) -> str:
        star_summary = dict(evidence.get("star_summary") or {})
        raw_category = str(
            evidence.get("category")
            or star_summary.get("category")
            or star_summary.get("type")
            or ""
        ).strip().lower()
        return raw_category

    def _render_alignment_evidence_label(
        self,
        evidence: dict[str, Any],
    ) -> str | None:
        for field in ("title", "snippet_text"):
            value = re.sub(r"\s+", " ", str(evidence.get(field) or "")).strip()
            display_value = make_user_facing_evidence_phrase(value)
            if display_value and display_value.lower() != "technology stack from resume":
                return (
                    display_value[:140].rsplit(" ", 1)[0]
                    if len(display_value) > 140
                    else display_value
                )
        skills = [
            self._normalize_display_skill(str(skill))
            for skill in evidence.get("skills") or []
            if str(skill).strip()
        ]
        return ", ".join(self._dedupe_preserve_order(skills)[:3]) or None

    def _requirement_supported_by_skills(
        self,
        *,
        requirement: str,
        selected_skill_keys: set[str],
    ) -> bool:
        requirement_key = self._normalize_display_skill(requirement).strip().lower()
        if requirement_key in selected_skill_keys:
            return True

        selected_text = " ".join(selected_skill_keys)
        requirement_lower = requirement_key
        support_markers = {
            "pytest": ("pytest", "test", "testing", "testclient"),
            "api": ("fastapi", "backend", "api"),
            "fastapi": ("fastapi", "backend", "api"),
            "backend": ("fastapi", "backend", "api"),
            "docker": ("docker", "container", "infrastructure"),
            "cicd": ("ci", "cd", "cicd", "pipeline"),
            "ci/cd": ("ci", "cd", "cicd", "pipeline"),
            "postgresql": ("postgres", "postgresql", "sqlalchemy"),
            "sqlalchemy": ("postgres", "postgresql", "sqlalchemy"),
            "workflow automation": ("workflow", "automation", "nocode", "no-code"),
            "git": ("git", "github", "repository", "version control"),
            "python": ("python",),
        }

        for marker, support_tokens in support_markers.items():
            if marker in requirement_lower and any(
                token in selected_text for token in support_tokens
            ):
                return True
        return False

    def _dedupe_vacancy_evidence_alignment(
        self,
        alignment: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in alignment:
            requirement = str(item.get("requirement") or "").strip()
            evidence = str(item.get("evidence") or "").strip()
            signature = (requirement.casefold(), evidence.casefold())
            if not requirement or signature in seen:
                continue
            seen.add(signature)
            result.append(item)
        return result

    def _display_relevance_label(self, value: str) -> str:
        normalized = value.strip().replace("_", " ")
        known = {
            "llm": "AI tooling",
            "chatgpt": "AI tooling",
            "prompt engineering": "Prompt engineering",
            "ai interaction": "AI interaction",
            "ai workflow": "Workflow automation",
            "automation": "Workflow automation",
            "automation tooling": "Workflow automation",
            "no-code": "Workflow automation",
            "python": "Python",
        }
        return known.get(normalized.lower(), normalized)

    def _normalize_display_skill(self, value: str) -> str:
        cleaned = re.sub(
            r"^(Technologies|AI tools|Automation tools)\s*:\s*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .;-–—•")

        replacements = {
            "llm": "LLM",
            "chatgpt": "ChatGPT",
            "openai": "OpenAI",
            "ai workflow": "AI Workflow",
            "no-code": "No-code",
        }
        return replacements.get(cleaned.lower(), cleaned)

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
            key = cleaned.casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result
