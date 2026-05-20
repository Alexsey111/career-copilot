# app\domain\interview_prep.py

from __future__ import annotations

import re
from typing import Any


def normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).casefold()


def tokenize_text(text: str | None) -> set[str]:
    return set(re.findall(r"[a-zа-я0-9]+", normalize_text(text)))


def build_competency_key(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", text.strip().lower())
    normalized = normalized.strip("_")
    return normalized or "general_competency"


def dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalize_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def achievement_search_text(achievement: dict[str, Any]) -> str:
    parts = [
        str(achievement.get("title") or ""),
        str(achievement.get("situation") or ""),
        str(achievement.get("task") or ""),
        str(achievement.get("action") or ""),
        str(achievement.get("result") or ""),
        str(achievement.get("metric_text") or ""),
        str(achievement.get("evidence_note") or ""),
    ]
    return " ".join(part for part in parts if part).strip().lower()


def has_metric_text(achievement: dict[str, Any]) -> bool:
    text = achievement_search_text(achievement)
    if re.search(r"\b\d+(\.\d+)?\b", text):
        return True

    metric_keywords = [
        "latency",
        "throughput",
        "requests per second",
        "rps",
        "users",
        "revenue",
        "conversion",
        "scale",
        "performance",
        "%",
    ]
    return any(keyword in text for keyword in metric_keywords)


def has_leadership_tokens(text: str) -> bool:
    leadership_keywords = [
        "lead",
        "led",
        "mentor",
        "mentored",
        "ownership",
        "architecture",
        "stakeholder",
        "coordination",
        "coordinated",
        "team",
    ]
    return any(keyword in text for keyword in leadership_keywords)


def infer_seniority_level(vacancy) -> str:
    text = normalize_text(
        " ".join(
            [
                getattr(vacancy, "title", "") or "",
                getattr(vacancy, "company", "") or "",
                getattr(vacancy, "location", "") or "",
                getattr(vacancy, "description_raw", "") or "",
            ]
        )
    )
    if any(keyword in text for keyword in ["principal", "staff"]):
        return "principal"
    if "lead" in text or "team lead" in text:
        return "lead"
    if "senior" in text:
        return "senior"
    if any(keyword in text for keyword in ["middle", "mid-level", "mid level", "mid"]):
        return "middle"
    if "junior" in text:
        return "junior"
    return "middle"


def infer_domain_expectations(vacancy, analysis) -> list[str]:
    analysis_keywords = ""
    must_have_items: list[dict[str, Any]] = []
    nice_to_have_items: list[dict[str, Any]] = []
    gap_items: list[dict[str, Any]] = []
    strength_items: list[dict[str, Any]] = []

    if analysis is not None:
        analysis_keywords = " ".join(str(keyword) for keyword in (analysis.keywords_json or []))
        must_have_items = analysis.must_have_json or []
        nice_to_have_items = analysis.nice_to_have_json or []
        gap_items = analysis.gaps_json or []
        strength_items = analysis.strengths_json or []

    vacancy_text = normalize_text(
        " ".join(
            [
                getattr(vacancy, "title", "") or "",
                getattr(vacancy, "company", "") or "",
                getattr(vacancy, "location", "") or "",
                getattr(vacancy, "description_raw", "") or "",
                analysis_keywords,
                " ".join(str(item.get("text", "")) for item in must_have_items),
                " ".join(str(item.get("text", "")) for item in nice_to_have_items),
                " ".join(str(item.get("keyword", "")) for item in gap_items),
                " ".join(str(item.get("keyword", "")) for item in strength_items),
            ]
        )
    )

    domain_map = [
        ("backend", ["backend", "api", "fastapi", "python", "postgres", "postgresql"]),
        ("platform", ["platform", "infrastructure", "infra", "kubernetes", "terraform", "devops"]),
        ("data", ["data", "analytics", "warehouse", "etl", "pipelines"]),
        ("ml/ai", ["ml", "ai", "llm", "machine learning", "neural"]),
        ("mobile", ["mobile", "android", "ios"]),
        ("frontend", ["frontend", "react", "vue", "typescript"]),
        ("product", ["product", "growth", "experimentation"]),
    ]

    domains: list[str] = []
    for label, keywords in domain_map:
        if any(keyword in vacancy_text for keyword in keywords):
            domains.append(label)

    if not domains:
        domains.append("general software delivery")

    return dedupe_preserve_order(domains)


def build_behavioral_signals(vacancy, analysis, required_skills: list[dict[str, Any]]) -> list[str]:
    signals: list[str] = []
    level = infer_seniority_level(vacancy)

    if level in {"senior", "lead", "staff", "principal"}:
        signals.extend(["ownership", "cross-functional collaboration", "mentoring"])
    elif level == "middle":
        signals.extend(["ownership", "communication", "collaboration"])
    else:
        signals.extend(["communication", "learning agility"])

    vacancy_text = normalize_text(
        " ".join(
            [
                getattr(vacancy, "title", "") or "",
                getattr(vacancy, "company", "") or "",
                getattr(vacancy, "location", "") or "",
                getattr(vacancy, "description_raw", "") or "",
                " ".join(str(keyword) for keyword in ((analysis.keywords_json or []) if analysis is not None else [])),
                " ".join(skill.get("label", "") for skill in required_skills),
            ]
        )
    )
    if "stakeholder" in vacancy_text and "stakeholder management" not in signals:
        signals.append("stakeholder management")
    if "ownership" in vacancy_text and "ownership" not in signals:
        signals.append("ownership")
    if "lead" in vacancy_text and "mentoring" not in signals:
        signals.append("mentoring")

    return dedupe_preserve_order(signals)


def build_seniority_expectations(vacancy) -> dict[str, Any]:
    level = infer_seniority_level(vacancy)
    if level in {"senior", "lead", "staff", "principal"}:
        signals = ["ownership", "architecture tradeoffs", "mentoring"]
    elif level == "middle":
        signals = ["independent delivery", "communication", "tradeoff reasoning"]
    else:
        signals = ["learning agility", "collaboration", "fundamentals"]

    return {
        "level": level,
        "signals": signals,
    }

