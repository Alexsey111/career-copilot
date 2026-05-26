# app\domain\evidence.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import hashlib
import re
from typing import Any, Mapping


class EvidenceSourceType(StrEnum):
    ACHIEVEMENT = "achievement"
    RESUME = "resume"
    RESUME_STRUCTURED = "resume_structured"
    GITHUB_PUBLIC = "github_public"
    INTERVIEW = "interview"
    MANUAL = "manual"


class EvidenceStrengthLevel(StrEnum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


class EvidenceFactStatus(StrEnum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    USER_PROVIDED = "user_provided"


@dataclass(slots=True)
class STAREvidenceSummary:
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None

    @property
    def is_complete(self) -> bool:
        return bool(
            str(self.situation or "").strip()
            and str(self.task or "").strip()
            and str(self.action or "").strip()
            and str(self.result or "").strip()
        )

    @property
    def summary(self) -> str:
        parts = [
            f"Situation: {self.situation}" if self.situation else "",
            f"Task: {self.task}" if self.task else "",
            f"Action: {self.action}" if self.action else "",
            f"Result: {self.result}" if self.result else "",
        ]
        return " ".join(part for part in parts if part).strip()

    def as_dict(self) -> dict[str, Any]:
        return {
            "situation": self.situation,
            "task": self.task,
            "action": self.action,
            "result": self.result,
            "summary": self.summary,
            "complete": self.is_complete,
        }


@dataclass(slots=True)
class EvidenceSnippet:
    id: str | None
    user_id: str
    title: str
    snippet_text: str
    source_type: EvidenceSourceType | str
    skills: list[str] = field(default_factory=list)
    evidence_strength: EvidenceStrengthLevel | str = EvidenceStrengthLevel.WEAK
    fact_status: EvidenceFactStatus | str = EvidenceFactStatus.UNVERIFIED
    usage_count: int = 0
    used_in_documents_count: int = 0
    used_in_interviews_count: int = 0
    star_summary: STAREvidenceSummary | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def normalized_source_type(self) -> str:
        return str(self.source_type or "").strip().lower()

    def normalized_strength(self) -> str:
        return str(self.evidence_strength or "").strip().lower()

    def normalized_fact_status(self) -> str:
        return str(self.fact_status or "").strip().lower()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "snippet_text": self.snippet_text,
            "source_type": self.normalized_source_type(),
            "skills": list(self.skills),
            "evidence_strength": self.normalized_strength(),
            "fact_status": self.normalized_fact_status(),
            "usage_count": self.usage_count,
            "used_in_documents_count": self.used_in_documents_count,
            "used_in_interviews_count": self.used_in_interviews_count,
            "star_summary": self.star_summary.as_dict() if self.star_summary else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass(slots=True)
class EvidenceUsage:
    id: str | None
    evidence_snippet_id: str
    user_id: str
    usage_type: str
    target_type: str | None = None
    target_id: str | None = None
    note: str | None = None
    created_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "evidence_snippet_id": self.evidence_snippet_id,
            "user_id": self.user_id,
            "usage_type": self.usage_type,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


SKILL_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "ai": (r"\bai\b", r"\bии\b", r"искусственн\w+\s+интеллект", r"нейросет"),
    "llm": (r"\bllm\b", r"large language model", r"языков\w+\s+модел"),
    "chatgpt": (r"\bchatgpt\b", r"\bчат[\s-]?gpt\b", r"\bчат[\s-]?бот"),
    "prompt_engineering": (r"\bprompt engineering\b", r"промпт", r"prompt"),
    "ai_interaction": (r"\bai interaction\b", r"llm tooling", r"работ[аы]\s+с\s+(?:ии|ai|llm)"),
    "ai_workflow": (r"\bai[-\s]?workflow\b", r"\bllm\s+workflow\b", r"\bai\s+pipeline\b"),
    "no_code": (r"\bno[-\s]?code\b", r"\bnocode\b", r"\blow[-\s]?code\b", r"без\s+кода"),
    "computer_vision": (
        r"\bcomputer vision\b",
        r"компьютерн\w+\s+зрени",
        r"изображени",
        r"\bвидео\b",
        r"мониторинг",
    ),
    "automation": (r"automat", r"автоматизац", r"автоматизирован"),
    "workflow": (r"\bworkflow\b", r"процесс", r"пайплайн", r"\bpipeline\b"),
    "python": (r"\bpython\b",),
    "fastapi": (r"\bfastapi\b", r"\bapi\b"),
    "postgresql": (r"\bpostgresql\b", r"\bpostgres\b"),
    "docker": (r"\bdocker\b",),
    "kubernetes": (r"\bkubernetes\b", r"\bk8s\b"),
    "redis": (r"\bredis\b",),
    "stakeholder_management": (r"\bstakeholder\b", r"\bstakeholders\b"),
    "leadership": (r"\blead\b", r"\bled\b", r"\bmentored?\b", r"\bownership\b"),
    "system_design": (r"\barchitecture\b", r"\bsystem design\b", r"\btradeoff\b"),
    "communication": (r"\bcommunication\b", r"\bcommunicat", r"\bpresented\b"),
    "testing": (r"\btesting\b", r"\bpytest\b", r"\bunittest\b"),
    "analytics": (r"\banalytics\b", r"\bdata\b", r"\bmetrics?\b"),
    "tensorflow": (r"\btensorflow\b",),
    "sql": (r"\bsql\b",),
    "git": (r"\bgit\b",),
}


def normalize_skill_tag(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9а-яё]+", "_", value.strip().lower())
    return cleaned.strip("_")


def extract_skill_tags(*texts: str | None) -> list[str]:
    combined = " ".join(str(text or "") for text in texts).lower()
    found: list[str] = []

    for tag, patterns in SKILL_KEYWORD_MAP.items():
        if any(re.search(pattern, combined) for pattern in patterns):
            found.append(tag)

    if "api" in combined and "fastapi" not in found:
        found.append("fastapi")

    if "stakeholder management" in combined and "stakeholder_management" not in found:
        found.append("stakeholder_management")

    if "leadership" in combined and "leadership" not in found:
        found.append("leadership")

    return dedupe_preserve_order(found)


def dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = normalize_skill_tag(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    return deduped


def build_star_summary(achievement: Mapping[str, Any]) -> STAREvidenceSummary:
    return STAREvidenceSummary(
        situation=str(achievement.get("situation") or "").strip() or None,
        task=str(achievement.get("task") or "").strip() or None,
        action=str(achievement.get("action") or "").strip() or None,
        result=str(achievement.get("result") or "").strip() or None,
    )


def build_evidence_text(achievement: Mapping[str, Any]) -> str:
    star = build_star_summary(achievement)
    parts = [
        str(achievement.get("title") or "").strip(),
        star.summary,
        str(achievement.get("metric_text") or "").strip(),
        str(achievement.get("evidence_note") or "").strip(),
    ]
    return " ".join(part for part in parts if part).strip()


def build_evidence_fingerprint(
    *,
    user_id: str,
    title: str,
    snippet_text: str,
    source_type: str,
    skills: list[str],
    fact_status: str,
) -> str:
    payload = "|".join(
        [
            user_id.strip().lower(),
            title.strip().lower(),
            snippet_text.strip().lower(),
            source_type.strip().lower(),
            ",".join(dedupe_preserve_order(skills)),
            fact_status.strip().lower(),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
