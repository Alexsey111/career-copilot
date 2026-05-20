# app\services\interview_question_service.py

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.domain.evidence import (
    EvidenceFactStatus,
    EvidenceStrengthLevel,
    build_star_summary,
    extract_skill_tags,
)
from app.domain.interview_prep import (
    achievement_search_text,
    build_behavioral_signals,
    build_competency_key,
    build_seniority_expectations,
    has_leadership_tokens,
    has_metric_text,
    infer_domain_expectations,
    tokenize_text,
)


class InterviewQuestionService:
    def build_competency_map(self, *, vacancy, analysis) -> dict[str, Any]:
        required_skills = self._dedupe_competencies(
            self._extract_requirement_items(analysis.must_have_json or []),
        )
        behavioral_signals = build_behavioral_signals(vacancy, analysis, required_skills)
        seniority = build_seniority_expectations(vacancy)
        domain_expectations = infer_domain_expectations(vacancy, analysis)

        return {
            "required_skills": required_skills,
            "behavioral_signals": behavioral_signals,
            "seniority_expectations": seniority,
            "domain_expectations": domain_expectations,
        }

    def build_question_set(
        self,
        *,
        vacancy,
        competency_map: dict[str, Any],
        confirmed_achievements: list[dict[str, Any]],
        weak_areas: list[dict[str, Any]],
        evidence_snippets: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        evidence_candidates = evidence_snippets or [
            self._achievement_to_evidence_item(achievement)
            for achievement in confirmed_achievements
        ]
        questions: list[dict[str, Any]] = []

        for skill in (competency_map.get("required_skills") or [])[:4]:
            prompt = (
                f"Расскажите о практическом опыте с {skill['label']} "
                f"в контексте вакансии {vacancy.title}."
            )
            questions.append(
                self._build_question(
                    category="technical",
                    prompt=prompt,
                    answer_format="STAR_or_example",
                    competency_key=skill["key"],
                    competency_name=skill["label"],
                    evidence_candidates=evidence_candidates,
                )
            )

        for signal in (competency_map.get("behavioral_signals") or [])[:2]:
            questions.append(
                self._build_question(
                    category="behavioral",
                    prompt=(
                        f"Приведите пример, где вы проявили {signal} "
                        f"в рабочем проекте."
                    ),
                    answer_format="STAR",
                    competency_key=build_competency_key(signal),
                    competency_name=signal,
                    evidence_candidates=evidence_candidates,
                )
            )

        seniority = competency_map.get("seniority_expectations") or {}
        if str(seniority.get("level") or "").lower() in {"senior", "lead", "staff", "principal"}:
            questions.append(
                self._build_question(
                    category="leadership",
                    prompt=(
                        "Как вы принимали архитектурные решения, "
                        "координировали других людей или помогали команде расти?"
                    ),
                    answer_format="STAR",
                    competency_key="leadership",
                    competency_name="Leadership",
                    evidence_candidates=evidence_candidates,
                )
            )

        if confirmed_achievements:
            top_achievement = self._select_top_achievement(
                confirmed_achievements,
                weak_areas,
            )
            if top_achievement:
                questions.append(
                    self._build_question(
                        category="project_deep_dive",
                        prompt=(
                            "Разберите этот проект или достижение глубже: "
                            f"{top_achievement['title']}."
                        ),
                        answer_format="STAR",
                        competency_key=build_competency_key(top_achievement["title"]),
                        competency_name=top_achievement["title"],
                        evidence_candidates=[
                            self._achievement_to_evidence_item(top_achievement)
                        ],
                    )
                )

        for weak_area in weak_areas[:3]:
            questions.append(
                self._build_question(
                    category="gap-risk",
                    prompt=(
                        f"Как вы честно ответите на вопрос о слабой зоне: "
                        f"{weak_area['message'].rstrip('.')}"
                    ),
                    answer_format="honest_gap_response",
                    competency_key=weak_area.get("competency_key"),
                    competency_name=weak_area.get("category") or weak_area["message"],
                    evidence_candidates=evidence_candidates,
                )
            )

        unique_questions: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for question in questions:
            question_id = str(question.get("question_id") or "")
            if not question_id or question_id in seen_ids:
                continue
            seen_ids.add(question_id)
            unique_questions.append(question)

        return unique_questions

    def build_evidence_links(
        self,
        *,
        questions: list[dict[str, Any]],
        confirmed_achievements: list[dict[str, Any]],
        evidence_snippets: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        evidence_candidates = evidence_snippets or [
            self._achievement_to_evidence_item(achievement)
            for achievement in confirmed_achievements
        ]
        links: list[dict[str, Any]] = []

        for question in questions:
            ranked = self._rank_evidence_items_for_question(
                question=question,
                evidence_items=evidence_candidates,
            )
            for item in ranked[:2]:
                links.append(
                    {
                        "question_id": question["question_id"],
                        "question_category": question["category"],
                        "competency_key": question.get("competency_key"),
                        "achievement_id": item["achievement_id"],
                        "achievement_title": item["title"],
                        "score": item["score"],
                        "reason": item["reason"],
                    }
                )

            question["recommended_evidence_ids"] = [
                item["achievement_id"] for item in ranked[:2]
            ]
            question["recommended_evidence"] = [
                {
                    "achievement_id": item["achievement_id"],
                    "title": item["title"],
                    "score": item["score"],
                    "reason": item["reason"],
                }
                for item in ranked[:2]
            ]

        return links

    def _build_question(
        self,
        *,
        category: str,
        prompt: str,
        answer_format: str,
        competency_key: str | None,
        competency_name: str | None,
        evidence_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        question_id = self._build_question_id(
            category=category,
            prompt=prompt,
            competency_key=competency_key,
            competency_name=competency_name,
        )
        ranked = self._rank_evidence_items_for_question(
            question={
                "question_id": question_id,
                "category": category,
                "prompt": prompt,
                "competency_key": competency_key,
                "competency_name": competency_name,
            },
            evidence_items=evidence_candidates,
        )

        return {
            "question_id": question_id,
            "category": category,
            "prompt": prompt,
            "answer_format": answer_format,
            "competency_key": competency_key,
            "competency_name": competency_name,
            "recommended_evidence_ids": [item["achievement_id"] for item in ranked[:2]],
            "recommended_evidence": [
                {
                    "achievement_id": item["achievement_id"],
                    "title": item["title"],
                    "score": item["score"],
                    "reason": item["reason"],
                }
                for item in ranked[:2]
            ],
        }

    def _rank_evidence_items_for_question(
        self,
        *,
        question: dict[str, Any],
        evidence_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not evidence_items:
            return []

        category = str(question.get("category") or "").lower()
        prompt = str(question.get("prompt") or "")
        competency_key = str(question.get("competency_key") or "").lower()
        competency_name = str(question.get("competency_name") or "").lower()
        query_tokens = tokenize_text(" ".join([prompt, competency_key, competency_name, category]))
        query_skills = set(extract_skill_tags(prompt, competency_key, competency_name, category))

        ranked: list[dict[str, Any]] = []
        for evidence in evidence_items:
            text = str(
                evidence.get("snippet_text")
                or evidence.get("title")
                or achievement_search_text(evidence)
            )
            text_tokens = tokenize_text(text)
            overlap = len(query_tokens & text_tokens)
            evidence_skills = {
                str(skill).strip().lower().replace(" ", "_")
                for skill in (evidence.get("skills") or [])
                if str(skill).strip()
            }
            if not overlap and competency_key and competency_key not in text:
                if not (query_skills & evidence_skills):
                    continue

            score = float(overlap)
            if competency_key and competency_key in text:
                score += 3.0
            if competency_name and competency_name in text:
                score += 2.0
            if category == "project_deep_dive" and self._has_metric_signal(evidence):
                score += 1.5
            if category == "leadership" and (
                has_leadership_tokens(text) or "leadership" in evidence_skills
            ):
                score += 2.5
            fact_status = str(evidence.get("fact_status") or "").lower()
            if fact_status == EvidenceFactStatus.CONFIRMED:
                score += 0.85
            elif fact_status == EvidenceFactStatus.PARTIAL:
                score += 0.2
            else:
                score -= 0.45
            if self._has_complete_star(evidence):
                score += 0.45
            elif self._has_partial_star(evidence):
                score += 0.12
            strength = str(evidence.get("evidence_strength") or "").lower()
            if strength == EvidenceStrengthLevel.STRONG:
                score += 0.75
            elif strength == EvidenceStrengthLevel.MEDIUM:
                score += 0.4
            elif str(evidence.get("fact_status") or "").lower() == EvidenceFactStatus.PARTIAL:
                score += 0.2
            usage_count = int(evidence.get("usage_count") or 0)
            if usage_count:
                score -= min(usage_count * 0.05, 0.3)

            ranked.append(
                {
                    "achievement_id": evidence.get("id") or evidence.get("achievement_id"),
                    "title": evidence.get("title") or "Evidence",
                    "score": round(score, 3),
                    "reason": self._build_evidence_reason(
                        question=question,
                        evidence=evidence,
                        overlap=overlap,
                    ),
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def _build_evidence_reason(
        self,
        *,
        question: dict[str, Any],
        evidence: dict[str, Any],
        overlap: int,
    ) -> str:
        parts = []
        category = str(question.get("category") or "").lower()
        if category:
            parts.append(category.replace("_", " "))
        if overlap:
            parts.append(f"{overlap} token matches")
        if self._has_metric_signal(evidence):
            parts.append("contains metrics")
        if has_leadership_tokens(str(evidence.get("snippet_text") or evidence.get("title") or "")):
            parts.append("contains leadership signal")
        return ", ".join(parts) or "closest confirmed achievement"

    def _achievement_to_evidence_item(self, achievement: dict[str, Any]) -> dict[str, Any]:
        text = achievement_search_text(achievement)
        star_summary = build_star_summary(achievement)
        fact_status_raw = str(achievement.get("fact_status") or "").strip().lower()
        if fact_status_raw == "confirmed":
            fact_status = EvidenceFactStatus.CONFIRMED
        elif fact_status_raw in {"needs_confirmation", "pending", "partial"}:
            fact_status = EvidenceFactStatus.PARTIAL
        else:
            fact_status = EvidenceFactStatus.UNVERIFIED

        skills = extract_skill_tags(
            str(achievement.get("title") or ""),
            str(achievement.get("metric_text") or ""),
            str(achievement.get("evidence_note") or ""),
            text,
        )
        if fact_status == EvidenceFactStatus.CONFIRMED and (
            achievement.get("metric_text") or star_summary.is_complete
        ):
            strength = EvidenceStrengthLevel.STRONG
        elif fact_status == EvidenceFactStatus.CONFIRMED or star_summary.summary:
            strength = EvidenceStrengthLevel.MEDIUM
        else:
            strength = EvidenceStrengthLevel.WEAK

        return {
            "id": achievement.get("id"),
            "achievement_id": achievement.get("id"),
            "title": achievement.get("title") or "Evidence",
            "snippet_text": text,
            "skills": skills,
            "evidence_strength": strength.value,
            "fact_status": fact_status.value,
            "usage_count": 0,
            "used_in_documents_count": 0,
            "used_in_interviews_count": 0,
            "star_summary": star_summary.as_dict(),
        }

    def _has_metric_signal(self, evidence: dict[str, Any]) -> bool:
        text = " ".join(
            str(evidence.get(field) or "")
            for field in ["snippet_text", "title", "evidence_note", "metric_text"]
        ).lower()
        if has_metric_text(evidence):
            return True
        return bool(
            re.search(r"\b\d+(\.\d+)?\b", text)
            or any(keyword in text for keyword in ["%", "latency", "throughput", "users", "requests"])
        )

    def _has_complete_star(self, evidence: dict[str, Any]) -> bool:
        star_summary = evidence.get("star_summary") or {}
        return all(
            str(star_summary.get(field) or "").strip()
            for field in ("situation", "task", "action", "result")
        )

    def _has_partial_star(self, evidence: dict[str, Any]) -> bool:
        star_summary = evidence.get("star_summary") or {}
        return any(
            str(star_summary.get(field) or "").strip()
            for field in ("situation", "task", "action", "result")
        )

    def _select_top_achievement(
        self,
        confirmed_achievements: list[dict[str, Any]],
        weak_areas: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not confirmed_achievements:
            return None

        weakness_text = " ".join(item["message"] for item in weak_areas)
        weakness_tokens = tokenize_text(weakness_text)
        ranked: list[tuple[float, dict[str, Any]]] = []
        for achievement in confirmed_achievements:
            text = achievement_search_text(achievement)
            tokens = tokenize_text(text)
            score = float(len(tokens & weakness_tokens))
            if has_metric_text(achievement):
                score += 1.5
            if has_leadership_tokens(text):
                score += 1.0
            ranked.append((score, achievement))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[0][1] if ranked else confirmed_achievements[0]

    def _extract_requirement_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        extracted: list[dict[str, Any]] = []
        for item in items or []:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            extracted.append(
                {
                    "key": build_competency_key(text),
                    "label": text,
                    "source": "must_have",
                    "weight": item.get("weight"),
                }
            )
        return extracted

    def _dedupe_competencies(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            key = item["key"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _build_question_id(
        *,
        category: str,
        prompt: str,
        competency_key: str | None,
        competency_name: str | None,
    ) -> str:
        payload = "|".join(
            [
                category,
                prompt,
                competency_key or "",
                competency_name or "",
            ]
        )
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
        return f"ipq_{digest}"
