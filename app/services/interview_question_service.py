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
    infer_domain_focus_areas,
    tokenize_text,
)


class InterviewQuestionService:
    def build_competency_map(
        self,
        *,
        vacancy,
        analysis,
        evidence_snippets: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        required_skills = self._dedupe_competencies(
            [
                *self._extract_requirement_items(analysis.must_have_json or [], source="must_have"),
                *self._extract_requirement_items(analysis.strengths_json or [], source="strength"),
                *self._extract_requirement_items(analysis.gaps_json or [], source="gap"),
            ],
        )
        evidence_competencies = self._extract_evidence_competencies(
            evidence_snippets or [],
            vacancy_competencies=required_skills,
        )
        behavioral_signals = build_behavioral_signals(vacancy, analysis, required_skills)
        seniority = build_seniority_expectations(vacancy)
        domain_focus_areas = infer_domain_focus_areas(vacancy, analysis)

        return {
            "required_skills": required_skills,
            "evidence_competencies": evidence_competencies,
            "behavioral_signals": behavioral_signals,
            "seniority_expectations": seniority,
            "domain_focus_areas": domain_focus_areas,
            "domain_expectations": domain_focus_areas,
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
            prompt = self._technical_question_prompt(
                skill_label=str(skill["label"]),
                vacancy_title=str(getattr(vacancy, "title", "") or ""),
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

        for competency in (competency_map.get("evidence_competencies") or [])[:3]:
            questions.append(
                self._build_question(
                    category="evidence_probe",
                    prompt=(
                        f"Расскажите подробнее про {competency['label']}: "
                        "какую задачу вы решали, какие инструменты использовали и какой был результат?"
                    ),
                    answer_format="STAR_or_project_context",
                    competency_key=competency["key"],
                    competency_name=competency["label"],
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
        else:
            top_evidence = self._select_top_evidence_item(evidence_candidates)
            if top_evidence:
                questions.append(
                    self._build_question(
                        category="project_deep_dive",
                        prompt=(
                            "Разберите этот проект или факт из резюме глубже: "
                            f"{top_evidence['title']}."
                        ),
                        answer_format="STAR_or_project_context",
                        competency_key=build_competency_key(str(top_evidence["title"])),
                        competency_name=str(top_evidence["title"]),
                        evidence_candidates=[top_evidence],
                    )
                )

        for weak_area in weak_areas[:3]:
            weak_label = self._weak_area_label(weak_area)
            questions.append(
                self._build_question(
                    category="gap-risk",
                    prompt=(
                        f"Как вы честно ответите на вопрос о слабой зоне: "
                        f"{weak_label.rstrip('.')}"
                    ),
                    answer_format="honest_gap_response",
                    competency_key=weak_area.get("competency_key"),
                    competency_name=(
                        weak_area.get("competency_name")
                        or weak_area.get("competency_label")
                        or weak_area.get("source_requirement")
                        or weak_label
                    ),
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
                    "source_type": item.get("source_type"),
                    "fact_status": item.get("fact_status"),
                    "skills": item.get("skills") or [],
                    "match_confidence": item.get("match_confidence"),
                    "match_type": item.get("match_type"),
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
        ranked = [
            item
            for item in ranked
            if item.get("match_confidence") in {"high", "medium"}
        ]
        if category == "behavioral":
            ranked = [
                item
                for item in ranked
                if item.get("match_confidence") == "high"
                or item.get("match_type") == "exact_requirement"
            ]
        recommended_evidence_ids = [
            item["achievement_id"]
            for item in ranked[:2]
            if item.get("achievement_id")
        ]
        source_type = "gap" if category == "gap-risk" else "vacancy_requirement"
        if category == "evidence_probe":
            source_type = "extracted_evidence"
        fact_status = (
            "inferred_needs_review"
            if category == "gap-risk"
            else self._question_fact_status(ranked[:2])
        )

        return {
            "question_id": question_id,
            "category": category,
            "prompt": prompt,
            "answer_format": answer_format,
            "competency_key": competency_key,
            "competency_name": competency_name,
            "source_type": source_type,
            "source_requirement": competency_name,
            "source_achievement_id": recommended_evidence_ids[0]
            if recommended_evidence_ids
            else None,
            "fact_status": fact_status,
            "requires_careful_answer": category == "gap-risk",
            "recommended_evidence_ids": recommended_evidence_ids,
            "recommended_evidence": [
                {
                    "achievement_id": item["achievement_id"],
                    "title": item["title"],
                    "score": item["score"],
                    "reason": item["reason"],
                    "source_type": item.get("source_type"),
                    "fact_status": item.get("fact_status"),
                    "skills": item.get("skills") or [],
                    "match_confidence": item.get("match_confidence"),
                    "match_type": item.get("match_type"),
                }
                for item in ranked[:2]
            ],
            "provenance": {
                "source_type": source_type,
                "source_requirement": competency_name,
                "source_achievement_id": recommended_evidence_ids[0]
                if recommended_evidence_ids
                else None,
                "recommended_evidence_ids": recommended_evidence_ids,
                "fact_status": fact_status,
                "requires_human_review": True,
                "requires_careful_answer": category == "gap-risk",
            },
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
            evidence_category = str(
                evidence.get("category")
                or (evidence.get("star_summary") or {}).get("category")
                or ""
            ).strip().lower()
            evidence_title = str(evidence.get("title") or "").strip().lower()
            if evidence_category == "technologies" or evidence_title == "technology stack from resume":
                continue

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
            elif fact_status == EvidenceFactStatus.USER_PROVIDED:
                score += 0.55
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

            match_confidence = self._evidence_match_confidence(
                score=score,
                overlap=overlap,
                evidence=evidence,
            )
            match_type = self._evidence_match_type(
                question=question,
                evidence=evidence,
                overlap=overlap,
            )

            ranked.append(
                {
                    "achievement_id": evidence.get("id") or evidence.get("achievement_id"),
                    "title": evidence.get("title") or "Evidence",
                    "source_type": evidence.get("source_type"),
                    "fact_status": evidence.get("fact_status"),
                    "skills": list(evidence.get("skills") or []),
                    "score": round(score, 3),
                    "match_confidence": match_confidence,
                    "match_type": match_type,
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
        parts: list[str] = []

        if overlap >= 2:
            parts.append("Совпадает с несколькими словами из вопроса")
        elif overlap == 1:
            parts.append("Есть слабое текстовое совпадение")

        if self._has_metric_signal(evidence):
            parts.append("Есть измеримый результат")

        fact_status = str(evidence.get("fact_status") or "").lower()
        if fact_status in {EvidenceFactStatus.CONFIRMED, EvidenceFactStatus.USER_PROVIDED}:
            parts.append("Факт подтверждён")
        else:
            parts.append("Факт требует подтверждения")

        return " · ".join(parts) or "Связь с вопросом требует проверки"

    def _evidence_match_confidence(
        self,
        *,
        score: float,
        overlap: int,
        evidence: dict[str, Any],
    ) -> str:
        fact_status = str(evidence.get("fact_status") or "").lower()

        if fact_status in {
            EvidenceFactStatus.CONFIRMED,
            EvidenceFactStatus.USER_PROVIDED,
        } and overlap >= 2:
            return "high"

        if overlap >= 2:
            return "medium"

        if fact_status in {
            EvidenceFactStatus.CONFIRMED,
            EvidenceFactStatus.USER_PROVIDED,
        } and overlap >= 1:
            return "medium"

        return "low"

    def _evidence_match_type(
        self,
        *,
        question: dict[str, Any],
        evidence: dict[str, Any],
        overlap: int,
    ) -> str:
        competency_key = str(question.get("competency_key") or "").lower()
        competency_name = str(question.get("competency_name") or "").lower()
        text = str(
            evidence.get("snippet_text")
            or evidence.get("title")
            or achievement_search_text(evidence)
        ).lower()

        if competency_key and competency_key in text:
            return "exact_requirement"

        if competency_name and competency_name in text:
            return "exact_requirement"

        if overlap >= 2:
            return "keyword_overlap"

        return "weak_overlap"

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

    def _question_fact_status(self, ranked_items: list[dict[str, Any]]) -> str:
        statuses = {
            str(item.get("fact_status") or "").strip().lower()
            for item in ranked_items
            if str(item.get("fact_status") or "").strip()
        }
        if "confirmed" in statuses:
            return "confirmed"
        if "user_provided" in statuses:
            return "user_provided"
        if statuses:
            return "needs_confirmation"
        return "needs_confirmation"

    def _select_top_evidence_item(
        self,
        evidence_items: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not evidence_items:
            return None
        ranked = sorted(
            evidence_items,
            key=lambda item: (
                1 if str(item.get("fact_status") or "").lower() == "confirmed" else 0,
                1 if str(item.get("fact_status") or "").lower() == "user_provided" else 0,
                1 if self._has_metric_signal(item) else 0,
                len(item.get("skills") or []),
            ),
            reverse=True,
        )
        return ranked[0]

    def _extract_requirement_items(
        self,
        items: list[dict[str, Any]],
        *,
        source: str,
    ) -> list[dict[str, Any]]:
        extracted: list[dict[str, Any]] = []
        for item in items or []:
            text = str(
                item.get("text")
                or item.get("keyword")
                or item.get("requirement_text")
                or ""
            ).strip()
            if not text:
                continue
            for label in self._normalize_requirement_labels(text):
                extracted.append(
                    {
                        "key": build_competency_key(label),
                        "label": label,
                        "source": source,
                        "weight": item.get("weight"),
                        "source_requirement": text,
                    }
                )
        return extracted

    def _normalize_requirement_labels(self, text: str) -> list[str]:
        labels: list[str] = []

        for group in re.findall(r"\(([^)]+)\)", text):
            labels.extend(self._split_requirement_list(group))

        known_tools = [
            "Adobe Photoshop",
            "CorelDRAW",
            "Corel Draw",
            "Adobe Illustrator",
            "Illustrator",
            "Figma",
            "InDesign",
        ]
        for tool in known_tools:
            if re.search(rf"(?<!\w){re.escape(tool)}(?!\w)", text, flags=re.IGNORECASE):
                labels.append("CorelDRAW" if tool == "Corel Draw" else tool)

        labels = self._dedupe_text(labels)
        return labels or [text]

    def _split_requirement_list(self, value: str) -> list[str]:
        parts = [
            part.strip(" .;:-–—•")
            for part in re.split(r"[,;/|]|\s+и\s+|\s+and\s+", value)
            if part.strip(" .;:-–—•")
        ]
        return [
            part
            for part in parts
            if re.search(r"[A-Za-zА-Яа-яЁё0-9]", part)
            and len(part) <= 50
        ]

    def _technical_question_prompt(self, *, skill_label: str, vacancy_title: str) -> str:
        label = skill_label.strip()
        if self._is_software_tool_label(label):
            return f"Расскажите о вашем опыте работы в {label}."
        if "макет" in label.lower() and "печ" in label.lower():
            return "Как вы готовили макеты к печати?"
        suffix = f" в контексте вакансии {vacancy_title}" if vacancy_title else ""
        return f"Расскажите о практическом опыте с {label}{suffix}."

    def _is_software_tool_label(self, value: str) -> bool:
        normalized = value.strip().lower()
        return normalized in {
            "adobe photoshop",
            "coreldraw",
            "adobe illustrator",
            "illustrator",
            "figma",
            "indesign",
        }

    def _weak_area_label(self, weak_area: dict[str, Any]) -> str:
        label = str(
            weak_area.get("competency_name")
            or weak_area.get("competency_label")
            or weak_area.get("source_requirement")
            or ""
        ).strip()
        if label:
            return label

        message = str(weak_area.get("message") or "").strip()
        match = re.match(r"^No confirmed (.+?) evidence(?:\.|$)", message, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return message

    def _dedupe_text(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = re.sub(r"\s+", " ", str(value)).strip()
            key = cleaned.casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    def _extract_evidence_competencies(
        self,
        evidence_snippets: list[dict[str, Any]],
        *,
        vacancy_competencies: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        vacancy_text = " ".join(
            str(item.get("label") or item.get("key") or "")
            for item in (vacancy_competencies or [])
        )
        vacancy_tokens = tokenize_text(vacancy_text)
        vacancy_keys = {
            str(item.get("key") or "").strip().lower()
            for item in (vacancy_competencies or [])
            if str(item.get("key") or "").strip()
        }
        allowed_keys = {
            *vacancy_keys,
        }
        allowed_labels = {
            str(item.get("label") or "").strip().lower()
            for item in (vacancy_competencies or [])
            if str(item.get("label") or "").strip()
        }
        items: list[dict[str, Any]] = []
        for evidence in evidence_snippets:
            source_type = str(evidence.get("source_type") or "").strip().lower()
            category = str(
                evidence.get("category")
                or (evidence.get("star_summary") or {}).get("category")
                or ""
            ).strip().lower()
            if source_type not in {"resume_structured", "github_public", "achievement", "manual"}:
                continue

            # Aggregated skill lists are useful as profile signals,
            # but they are not interview stories and must not become evidence_probe questions.
            if category == "technologies":
                continue

            if category and category not in {
                "ai_project",
                "automation",
                "prompt_engineering",
                "workflow_experience",
                "competency_signal",
                "project",
                "achievement",
            }:
                continue
            for skill in evidence.get("skills") or []:
                label = str(skill).strip()
                if not label:
                    continue
                skill_key = build_competency_key(label)
                skill_tokens = tokenize_text(label)

                if vacancy_tokens or vacancy_keys:
                    has_overlap = bool(skill_tokens & vacancy_tokens) or skill_key in vacancy_keys
                    if not has_overlap:
                        continue

                if (allowed_keys or allowed_labels) and (
                    skill_key not in allowed_keys
                    and label.lower() not in allowed_labels
                    and not (tokenize_text(label) & vacancy_tokens)
                ):
                    continue
                items.append(
                    {
                        "key": skill_key,
                        "label": label,
                        "source": source_type or "evidence_bank",
                        "evidence_id": evidence.get("id"),
                        "evidence_title": evidence.get("title"),
                        "fact_status": evidence.get("fact_status"),
                    }
                )
        return self._dedupe_competencies(items)

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
