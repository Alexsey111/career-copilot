# app\services\evidence_extraction_service.py

from __future__ import annotations

from typing import Any, Mapping

from app.domain.evidence import (
    EvidenceFactStatus,
    EvidenceSnippet,
    EvidenceSourceType,
    build_evidence_fingerprint,
    build_evidence_text,
    build_star_summary,
    extract_skill_tags,
    normalize_skill_tag,
)
from app.services.evidence_strength_service import EvidenceStrengthService


class EvidenceExtractionService:
    def __init__(self, strength_service: EvidenceStrengthService | None = None) -> None:
        self.strength_service = strength_service or EvidenceStrengthService()

    def extract_from_achievement(
        self,
        achievement: Mapping[str, Any],
        *,
        user_id: str,
        source_type: EvidenceSourceType | str = EvidenceSourceType.ACHIEVEMENT,
    ) -> EvidenceSnippet:
        title = str(achievement.get("title") or "").strip() or "Achievement evidence"
        snippet_text = build_evidence_text(achievement)
        star_summary = build_star_summary(achievement)
        skills = extract_skill_tags(
            title,
            snippet_text,
            str(achievement.get("metric_text") or ""),
            str(achievement.get("evidence_note") or ""),
        )
        fact_status = self._normalize_fact_status(str(achievement.get("fact_status") or ""))
        strength = self.strength_service.classify_strength(
            self.strength_service.calculate_strength_score(
                {
                    "title": title,
                    "snippet_text": snippet_text,
                    "metric_text": achievement.get("metric_text"),
                    "evidence_note": achievement.get("evidence_note"),
                    "fact_status": fact_status,
                    "skills": skills,
                    "star_summary": star_summary,
                }
            )
        )
        return EvidenceSnippet(
            id=str(achievement.get("id") or "").strip() or None,
            user_id=user_id,
            title=title,
            snippet_text=snippet_text,
            source_type=source_type,
            skills=skills,
            evidence_strength=strength,
            fact_status=fact_status,
            usage_count=0,
            used_in_documents_count=0,
            used_in_interviews_count=0,
            star_summary=star_summary,
        )

    def extract_from_text(
        self,
        *,
        title: str,
        text: str,
        user_id: str,
        source_type: EvidenceSourceType | str,
        fact_status: EvidenceFactStatus | str = EvidenceFactStatus.UNVERIFIED,
    ) -> EvidenceSnippet:
        snippet_text = str(text or "").strip()
        skills = extract_skill_tags(title, snippet_text)
        normalized_fact_status = self._normalize_fact_status(str(fact_status))
        strength = self.strength_service.classify_strength(
            self.strength_service.calculate_strength_score(
                {
                    "title": title,
                    "snippet_text": snippet_text,
                    "fact_status": normalized_fact_status,
                    "skills": skills,
                }
            )
        )
        return EvidenceSnippet(
            id=None,
            user_id=user_id,
            title=title,
            snippet_text=snippet_text,
            source_type=source_type,
            skills=skills,
            evidence_strength=strength,
            fact_status=normalized_fact_status,
            usage_count=0,
            used_in_documents_count=0,
            used_in_interviews_count=0,
            star_summary=None,
        )

    def extract_from_achievements(
        self,
        achievements: list[Mapping[str, Any]],
        *,
        user_id: str,
        source_type: EvidenceSourceType | str = EvidenceSourceType.ACHIEVEMENT,
    ) -> list[EvidenceSnippet]:
        snippets: list[EvidenceSnippet] = []
        seen: set[str] = set()

        for achievement in achievements or []:
            title = str(achievement.get("title") or "").strip()
            if not title:
                continue

            snippet = self.extract_from_achievement(
                achievement,
                user_id=user_id,
                source_type=source_type,
            )
            fingerprint = build_evidence_fingerprint(
                user_id=user_id,
                title=snippet.title,
                snippet_text=snippet.snippet_text,
                source_type=str(snippet.source_type),
                skills=snippet.skills,
                fact_status=snippet.fact_status,
            )
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            snippets.append(snippet)

        return snippets

    def snippet_to_dict(self, snippet: EvidenceSnippet) -> dict[str, Any]:
        return {
            "id": snippet.id,
            "user_id": snippet.user_id,
            "title": snippet.title,
            "snippet_text": snippet.snippet_text,
            "source_type": str(snippet.source_type),
            "skills": list(snippet.skills),
            "evidence_strength": str(snippet.evidence_strength),
            "fact_status": str(snippet.fact_status),
            "usage_count": snippet.usage_count,
            "used_in_documents_count": snippet.used_in_documents_count,
            "used_in_interviews_count": snippet.used_in_interviews_count,
            "star_summary": snippet.star_summary.as_dict() if snippet.star_summary else {},
            "fingerprint": build_evidence_fingerprint(
                user_id=snippet.user_id,
                title=snippet.title,
                snippet_text=snippet.snippet_text,
                source_type=str(snippet.source_type),
                skills=snippet.skills,
                fact_status=str(snippet.fact_status),
            ),
        }

    def _normalize_fact_status(self, value: str) -> str:
        normalized = normalize_skill_tag(value)
        if normalized == "confirmed":
            return EvidenceFactStatus.CONFIRMED
        if normalized == "user_provided":
            return EvidenceFactStatus.USER_PROVIDED
        if normalized in {"partial", "needs_confirmation", "pending"}:
            return EvidenceFactStatus.PARTIAL
        return EvidenceFactStatus.UNVERIFIED
