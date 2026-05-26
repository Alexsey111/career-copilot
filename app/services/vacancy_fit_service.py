# app\services\vacancy_fit_service.py

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interview_prep import has_leadership_tokens
from app.domain.skills.utils import get_related_skills, keyword_present
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.evidence_snippet_repository import EvidenceSnippetRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository


@dataclass(frozen=True)
class RequirementSignal:
    requirement: str
    keyword: str
    scope: str
    requirement_text: str | None
    weight: int


class VacancyFitService:
    def __init__(
        self,
        vacancy_repository: VacancyRepository | None = None,
        vacancy_analysis_repository: VacancyAnalysisRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        evidence_snippet_repository: EvidenceSnippetRepository | None = None,
    ) -> None:
        self.vacancy_repo = vacancy_repository or VacancyRepository()
        self.analysis_repo = vacancy_analysis_repository or VacancyAnalysisRepository()
        self.profile_repo = candidate_profile_repository or CandidateProfileRepository()
        self.evidence_repo = evidence_snippet_repository or EvidenceSnippetRepository()

    async def build_vacancy_fit(
        self,
        session: AsyncSession,
        *,
        vacancy_id: UUID,
        user_id: UUID,
    ) -> dict:
        vacancy = await self.vacancy_repo.get_by_id(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        analysis = await self.analysis_repo.get_latest_for_vacancy(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="vacancy analysis not found; run vacancy analysis first",
            )

        profile = await self.profile_repo.get_with_related_by_user_id(session, user_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="candidate profile not found; run profile extraction first",
            )

        snippets = await self.evidence_repo.list_by_user_id(session, user_id=user_id)

        signals = self._build_requirement_signals(
            must_have=analysis.must_have_json or [],
            nice_to_have=analysis.nice_to_have_json or [],
            keywords=analysis.keywords_json or [],
        )
        if not signals:
            signals = self._build_requirement_signals(
                must_have=[],
                nice_to_have=[],
                keywords=analysis.keywords_json or [],
            )

        profile_corpus = self._build_profile_corpus(profile)
        experience_corpus = self._build_experience_corpus(profile)
        vacancy_text = self._build_vacancy_text(vacancy, analysis)
        leadership_required = self._vacancy_requires_leadership(vacancy_text)

        requirements: list[dict] = []
        grouped: dict[str, list[dict]] = {"strong": [], "medium": [], "missing": []}

        total_weight = sum(item.weight for item in signals) or 1
        matched_skill_weight = 0
        matched_experience_weight = 0
        matched_evidence_weight = 0
        leadership_fit_weight = 0
        leadership_total_weight = 0

        for signal in signals:
            profile_supported = self._profile_satisfies_keyword(signal.keyword, profile_corpus)
            experience_supported = self._experience_satisfies_keyword(
                signal.keyword,
                experience_corpus,
            )
            evidence_matches = self._find_evidence_matches(
                snippets,
                keyword=signal.keyword,
            )
            usable_matches = [
                match
                for match in evidence_matches
                if str(match.get("fact_status") or "").strip().lower()
                in {"confirmed", "user_provided", "needs_confirmation"}
            ]

            coverage_level = self._coverage_level_for_matches(usable_matches)
            severity = self._gap_severity_for_signal(
                signal=signal,
                profile_supported=profile_supported,
                experience_supported=experience_supported,
                coverage_level=coverage_level,
            )

            if profile_supported:
                matched_skill_weight += signal.weight
            if experience_supported:
                matched_experience_weight += signal.weight

            if usable_matches:
                matched_evidence_weight += signal.weight * self._coverage_score_ratio(coverage_level)

            requirement_item = {
                "requirement": signal.requirement,
                "scope": signal.scope,
                "severity": severity,
                "coverage_level": coverage_level,
                "reason": self._build_requirement_reason(
                    signal=signal,
                    profile_supported=profile_supported,
                    experience_supported=experience_supported,
                    confirmed_matches=usable_matches,
                    evidence_matches=evidence_matches,
                ),
                "evidence_ids": [
                    match["evidence_id"]
                    for match in usable_matches
                    if match.get("evidence_id")
                ],
                "supporting_evidence": usable_matches,
            }
            requirements.append(requirement_item)

            if coverage_level == "strong":
                grouped["strong"].append(requirement_item)
            elif coverage_level == "medium":
                grouped["medium"].append(requirement_item)
            else:
                grouped["missing"].append(requirement_item)

            if self._is_leadership_signal(signal.keyword):
                leadership_total_weight += signal.weight
                if profile_supported:
                    leadership_fit_weight += signal.weight
                if usable_matches:
                    leadership_fit_weight += signal.weight * self._coverage_score_ratio(coverage_level) * 0.5

        skills_fit = round((matched_skill_weight / total_weight) * 100)
        experience_fit = round((matched_experience_weight / total_weight) * 100)
        evidence_fit = round((matched_evidence_weight / total_weight) * 100)
        leadership_fit = 100
        if leadership_required or leadership_total_weight:
            leadership_fit = self._calculate_leadership_fit(
                profile_corpus=profile_corpus,
                experience_corpus=experience_corpus,
                requirements=requirements,
            )

        overall_fit_score = self._calculate_overall_fit_score(
            skills_fit=skills_fit,
            evidence_fit=evidence_fit,
            experience_fit=experience_fit,
            leadership_fit=leadership_fit,
            leadership_required=leadership_required,
        )

        gap_severity = self._overall_gap_severity(requirements)
        readiness_recommendation = self._readiness_recommendation(
            overall_fit_score=overall_fit_score,
            gap_severity=gap_severity,
            evidence_fit=evidence_fit,
        )

        required = [signal.requirement for signal in signals]
        return {
            "analysis_id": analysis.id,
            "analysis_version": analysis.analysis_version,
            "vacancy_id": vacancy.id,
            "overall_fit_score": overall_fit_score,
            "skills_fit": skills_fit,
            "evidence_fit": evidence_fit,
            "experience_fit": experience_fit,
            "leadership_fit": leadership_fit,
            "gap_severity": gap_severity,
            "readiness_recommendation": readiness_recommendation,
            "requirements": requirements,
            "evidence_coverage": {
                "required": required,
                "strong": grouped["strong"],
                "medium": grouped["medium"],
                "missing": grouped["missing"],
            },
        }

    def _build_requirement_signals(
        self,
        *,
        must_have: list[dict],
        nice_to_have: list[dict],
        keywords: list[str],
    ) -> list[RequirementSignal]:
        items: list[RequirementSignal] = []

        for requirement_text in must_have:
            label = str(requirement_text.get("text") or requirement_text.get("keyword") or "").strip()
            extracted = self._extract_keywords(label) or ([label] if label else [])
            for keyword in extracted:
                items.append(
                    RequirementSignal(
                        requirement=label or keyword,
                        keyword=keyword,
                        scope="must_have",
                        requirement_text=label or None,
                        weight=3,
                    )
                )

        for requirement_text in nice_to_have:
            label = str(requirement_text.get("text") or requirement_text.get("keyword") or "").strip()
            extracted = self._extract_keywords(label) or ([label] if label else [])
            for keyword in extracted:
                items.append(
                    RequirementSignal(
                        requirement=label or keyword,
                        keyword=keyword,
                        scope="nice_to_have",
                        requirement_text=label or None,
                        weight=1,
                    )
                )

        if not items:
            for keyword in keywords:
                cleaned = str(keyword or "").strip()
                if not cleaned:
                    continue
                items.append(
                    RequirementSignal(
                        requirement=cleaned,
                        keyword=cleaned,
                        scope="keyword",
                        requirement_text=None,
                        weight=2,
                    )
                )

        return self._dedupe_requirement_signals(items)

    def _dedupe_requirement_signals(
        self,
        items: list[RequirementSignal],
    ) -> list[RequirementSignal]:
        seen: set[tuple[str, str]] = set()
        result: list[RequirementSignal] = []
        for item in items:
            key = (item.keyword.casefold(), item.scope)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _build_profile_corpus(self, profile) -> str:
        parts: list[str] = []
        for field in ("full_name", "headline", "location", "summary"):
            value = getattr(profile, field, None)
            if value:
                parts.append(str(value))

        target_roles = getattr(profile, "target_roles_json", None) or []
        parts.extend(str(item) for item in target_roles if item)

        for experience in getattr(profile, "experiences", []) or []:
            for field in ("company", "role", "description_raw"):
                value = getattr(experience, field, None)
                if value:
                    parts.append(str(value))

        for achievement in getattr(profile, "achievements", []) or []:
            for field in ("title", "situation", "task", "action", "result", "metric_text", "evidence_note"):
                value = getattr(achievement, field, None)
                if value:
                    parts.append(str(value))

        return "\n".join(parts)

    def _build_experience_corpus(self, profile) -> str:
        parts: list[str] = []
        for experience in getattr(profile, "experiences", []) or []:
            for field in ("company", "role", "description_raw"):
                value = getattr(experience, field, None)
                if value:
                    parts.append(str(value))
        return "\n".join(parts)

    def _build_vacancy_text(self, vacancy, analysis) -> str:
        parts = [
            getattr(vacancy, "title", "") or "",
            getattr(vacancy, "company", "") or "",
            getattr(vacancy, "location", "") or "",
            getattr(vacancy, "description_raw", "") or "",
            " ".join(str(item.get("text") or "") for item in (analysis.must_have_json or [])),
            " ".join(str(item.get("text") or "") for item in (analysis.nice_to_have_json or [])),
            " ".join(str(item) for item in (analysis.keywords_json or [])),
        ]
        return "\n".join(part for part in parts if part)

    def _vacancy_requires_leadership(self, vacancy_text: str) -> bool:
        normalized = vacancy_text.casefold()
        if has_leadership_tokens(normalized):
            return True
        return any(keyword in normalized for keyword in ["lead", "senior", "staff", "principal", "manager"])

    def _is_leadership_signal(self, value: str) -> bool:
        normalized = value.casefold()
        leadership_keywords = [
            "lead",
            "leadership",
            "leader",
            "stakeholder",
            "ownership",
            "cross-functional",
            "cross functional",
            "mentoring",
            "mentor",
            "coordination",
            "communication",
        ]
        return any(keyword in normalized for keyword in leadership_keywords)

    def _profile_satisfies_keyword(self, keyword: str, corpus: str) -> bool:
        if keyword_present(keyword, corpus):
            return True

        for related in get_related_skills(keyword):
            if keyword_present(related, corpus):
                return True
        return False

    def _experience_satisfies_keyword(self, keyword: str, corpus: str) -> bool:
        if not corpus.strip():
            return False
        if keyword_present(keyword, corpus):
            return True
        for related in get_related_skills(keyword):
            if keyword_present(related, corpus):
                return True
        return False

    def _find_evidence_matches(
        self,
        snippets,
        *,
        keyword: str,
    ) -> list[dict]:
        matches: list[dict] = []
        for snippet in snippets:
            score, reason = self._score_evidence_snippet(snippet, keyword)
            if score <= 0:
                continue
            matches.append(
                {
                    "evidence_id": snippet.id,
                    "title": snippet.title,
                    "reason": reason,
                    "score": score,
                    "fact_status": snippet.fact_status,
                    "evidence_strength": snippet.evidence_strength,
                    "star_preview": self._star_preview(snippet.star_summary_json),
                    "snippet_text": snippet.snippet_text,
                }
            )

        matches.sort(
            key=lambda item: (
                float(item.get("score") or 0.0),
                str(item.get("evidence_strength") or ""),
                str(item.get("fact_status") or ""),
            ),
            reverse=True,
        )
        return matches

    def _score_evidence_snippet(self, snippet, keyword: str) -> tuple[float, str]:
        keyword_norm = keyword.casefold()
        snippet_text = self._snippet_search_text(snippet)
        skills = {str(item).casefold() for item in (snippet.skills_json or []) if str(item).strip()}
        star_text = self._star_summary_text(snippet.star_summary_json)

        direct_match = keyword_norm in skills
        corpus_match = keyword_present(keyword, snippet_text) or keyword_present(keyword, star_text)
        related_match = any(
            keyword_present(related, snippet_text) or keyword_present(related, star_text)
            for related in get_related_skills(keyword)
        )

        if not (direct_match or corpus_match or related_match):
            return 0.0, ""

        if direct_match:
            base = 1.0
            match_reason = "skills overlap"
        elif corpus_match:
            base = 0.8
            match_reason = "snippet text overlap"
        else:
            base = 0.65
            match_reason = "related skill overlap"

        strength_factor = {
            "strong": 1.0,
            "medium": 0.75,
            "weak": 0.45,
        }.get(str(snippet.evidence_strength or "weak").strip().lower(), 0.45)
        fact_factor = {
            "confirmed": 1.0,
            "user_provided": 0.85,
            "partial": 0.8,
            "needs_confirmation": 0.55,
            "unverified": 0.55,
            "rejected": 0.2,
        }.get(str(snippet.fact_status or "unverified").strip().lower(), 0.55)

        score = round(base * strength_factor * fact_factor * 100, 1)
        reason = f"{match_reason}; strength={snippet.evidence_strength}; fact_status={snippet.fact_status}"
        return score, reason

    def _snippet_search_text(self, snippet) -> str:
        parts = [
            str(snippet.title or ""),
            str(snippet.snippet_text or ""),
            " ".join(str(item) for item in (snippet.skills_json or [])),
            self._star_summary_text(snippet.star_summary_json),
        ]
        return "\n".join(part for part in parts if part)

    def _star_summary_text(self, star_summary: dict | None) -> str:
        if not isinstance(star_summary, dict):
            return ""
        return " ".join(
            str(star_summary.get(field) or "")
            for field in ("situation", "task", "action", "result")
        ).strip()

    def _star_preview(self, star_summary: dict | None) -> dict[str, str]:
        if not isinstance(star_summary, dict):
            return {}
        preview: dict[str, str] = {}
        for field in ("situation", "task", "action", "result"):
            value = str(star_summary.get(field) or "").strip()
            if value:
                preview[field] = value
        return preview

    def _coverage_level_for_matches(self, confirmed_matches: list[dict]) -> str:
        if not confirmed_matches:
            return "none"

        top_score = float(confirmed_matches[0].get("score") or 0.0)
        if top_score >= 80:
            return "strong"
        if top_score >= 55:
            return "medium"
        return "none"

    def _coverage_score_ratio(self, coverage_level: str) -> float:
        return {
            "strong": 1.0,
            "medium": 0.7,
            "none": 0.0,
        }.get(coverage_level, 0.0)

    def _gap_severity_for_signal(
        self,
        *,
        signal: RequirementSignal,
        profile_supported: bool,
        experience_supported: bool,
        coverage_level: str,
    ) -> str:
        if coverage_level == "strong":
            return "minor"

        if signal.scope == "must_have":
            if profile_supported or experience_supported:
                return "important"
            return "critical"

        return "minor"

    def _overall_gap_severity(self, requirements: list[dict]) -> str:
        severities = [item.get("severity") for item in requirements if item.get("severity")]
        if "critical" in severities:
            return "critical"
        if "important" in severities:
            return "important"
        return "minor"

    def _calculate_leadership_fit(
        self,
        *,
        profile_corpus: str,
        experience_corpus: str,
        requirements: list[dict],
    ) -> int:
        leadership_requirements = [
            item for item in requirements if self._is_leadership_signal(str(item.get("requirement") or ""))
        ]
        if not leadership_requirements:
            return 100

        total_weight = max(1, len(leadership_requirements))
        score = 0.0
        for item in leadership_requirements:
            requirement = str(item.get("requirement") or "")
            signal_score = 0.0
            if self._profile_satisfies_keyword(requirement, profile_corpus):
                signal_score += 0.5
            if self._experience_satisfies_keyword(requirement, experience_corpus):
                signal_score += 0.25
            if item.get("coverage_level") in {"strong", "medium"}:
                signal_score += 0.25
            score += min(1.0, signal_score)

        return round((score / total_weight) * 100)

    def _calculate_overall_fit_score(
        self,
        *,
        skills_fit: int,
        evidence_fit: int,
        experience_fit: int,
        leadership_fit: int,
        leadership_required: bool,
    ) -> int:
        weights = {
            "skills_fit": 0.4,
            "evidence_fit": 0.35,
            "experience_fit": 0.25,
            "leadership_fit": 0.0 if not leadership_required else 0.1,
        }
        if not leadership_required:
            weights["skills_fit"] = 0.45
            weights["evidence_fit"] = 0.35
            weights["experience_fit"] = 0.2

        total_weight = sum(weights.values()) or 1.0
        weighted_score = (
            skills_fit * weights["skills_fit"]
            + evidence_fit * weights["evidence_fit"]
            + experience_fit * weights["experience_fit"]
            + leadership_fit * weights["leadership_fit"]
        ) / total_weight

        gap_penalty = 0
        if evidence_fit < 45:
            gap_penalty += 10
        if skills_fit < 55:
            gap_penalty += 5

        return max(0, min(100, round(weighted_score) - gap_penalty))

    def _readiness_recommendation(
        self,
        *,
        overall_fit_score: int,
        gap_severity: str,
        evidence_fit: int,
    ) -> str:
        if gap_severity == "critical" or evidence_fit < 45:
            return "Large evidence gaps"
        if overall_fit_score >= 75 and evidence_fit >= 65:
            return "Ready to apply"
        return "Apply with caution"

    def _build_requirement_reason(
        self,
        *,
        signal: RequirementSignal,
        profile_supported: bool,
        experience_supported: bool,
        confirmed_matches: list[dict],
        evidence_matches: list[dict],
    ) -> str:
        if confirmed_matches:
            best = confirmed_matches[0]
            return (
                f"Confirmed evidence found: {best.get('title')} "
                f"({best.get('evidence_strength')}, {best.get('fact_status')})."
            )
        if evidence_matches:
            best = evidence_matches[0]
            return (
                f"Matched evidence is not confirmed yet: {best.get('title')} "
                f"({best.get('evidence_strength')}, {best.get('fact_status')})."
            )
        if profile_supported and experience_supported:
            return "Supported by profile and work history, but no confirmed evidence snippet was found."
        if profile_supported:
            return "Supported by profile keywords, but no confirmed evidence snippet was found."
        if experience_supported:
            return "Supported by work history, but no confirmed evidence snippet was found."
        return "No confirmed evidence or profile overlap found."

    def _extract_keywords(self, text: str) -> list[str]:
        if not text:
            return []
        from app.services.vacancy_analysis_service import VacancyAnalysisService

        return VacancyAnalysisService()._extract_keywords("", text)
