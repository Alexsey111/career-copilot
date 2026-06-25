# app\services\interview_readiness_service.py

from __future__ import annotations

import re
from typing import Any

from app.domain.interview_prep import (
    achievement_search_text,
    InterviewReadinessRoadmap,
    InterviewReadinessRoadmapStep,
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
        vacancy_context_tokens = self._domain_context_tokens(
            competency_map=competency_map,
        )
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
                vacancy_context_tokens=vacancy_context_tokens,
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
                    "competency_label": skill["label"],
                    "source_requirement": (
                        skill.get("source_requirement") or skill["label"]
                    ),
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
            competency_map=competency_map,
        ):
            weak_areas.append(
                {
                    "code": "missing_domain_context",
                    "message": "Нет подтверждённого опыта в предметной области вакансии",
                    "severity": "warning",
                    "category": "domain",
                    "competency_key": "domain_context",
                    "competency_label": "Предметная область вакансии",
                    "source_requirement": "Предметная область вакансии",
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
        questions: list[dict[str, Any]] | None = None,
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

        question_ids_with_evidence = {
            str(link.get("question_id") or "").strip()
            for link in evidence_links
            if str(link.get("question_id") or "").strip()
        }
        question_coverage_score = min(100, len(question_ids_with_evidence) * 20)

        score = max(
            round(coverage_ratio * 100),
            question_coverage_score,
        )
        score -= len(blockers) * 20
        score -= len(warnings) * 8
        score -= self._answer_quality_penalty(questions)
        score = max(0, min(100, score))

        has_weak_answers = self._has_weak_answer_quality(questions)
        if has_weak_answers:
            warnings.append("Есть ответы, которые требуют доработки перед интервью")

        ready = not blockers and score >= 60 and not has_weak_answers
        roadmap = self._build_readiness_roadmap(
            score=score,
            weak_areas=weak_areas,
            questions=questions or [],
        )
        explanation = self._build_readiness_explanation(
            score=score,
            weak_areas=weak_areas,
            blockers=blockers,
            warnings=warnings,
        )
        return {
            "ready": ready,
            "blockers": blockers,
            "warnings": warnings,
            "score": score,
            "roadmap": roadmap.as_dict(),
            "explanation": explanation,
        }

    def _answer_quality_penalty(
        self,
        questions: list[dict[str, Any]] | None,
    ) -> int:
        penalty = 0

        for question in questions or []:
            answer = question.get("suggested_answer") or {}
            if not isinstance(answer, dict):
                continue

            answer_quality = (
                question.get("answer_quality")
                or answer.get("quality")
                or {}
            )
            if not isinstance(answer_quality, dict):
                continue

            score = answer_quality.get("score")
            if score is None:
                continue

            try:
                score_value = int(score)
            except (TypeError, ValueError):
                continue

            if score_value < 50:
                penalty += 20
            elif score_value < 70:
                penalty += 10

        return min(penalty, 40)

    def _has_weak_answer_quality(
        self,
        questions: list[dict[str, Any]] | None,
    ) -> bool:
        for question in questions or []:
            answer = question.get("suggested_answer") or {}
            if not isinstance(answer, dict):
                continue

            quality = (
                question.get("answer_quality")
                or answer.get("quality")
                or {}
            )
            if not isinstance(quality, dict):
                continue

            try:
                score = int(quality.get("score"))
            except (TypeError, ValueError):
                continue

            if score < 50:
                return True

        return False

    def _build_readiness_roadmap(
        self,
        *,
        score: int,
        weak_areas: list[dict[str, Any]],
        questions: list[dict[str, Any]] | None = None,
    ) -> InterviewReadinessRoadmap:
        if score >= 100:
            return InterviewReadinessRoadmap(
                current_score=score,
                projected_score=score,
                steps=[],
            )

        steps: list[InterviewReadinessRoadmapStep] = []

        for weak_area in weak_areas:
            category = str(weak_area.get("category") or "").strip().lower()

            if category == "technical":
                label = (
                    weak_area.get("competency_label")
                    or weak_area.get("source_requirement")
                    or weak_area.get("competency_key")
                    or "этой зоне"
                )
                steps.append(
                    InterviewReadinessRoadmapStep(
                        order=0,
                        title=f"Подтвердить опыт {label}",
                        expected_gain=15,
                    )
                )
            elif category == "leadership":
                steps.append(
                    InterviewReadinessRoadmapStep(
                        order=0,
                        title="Добавить пример лидерства",
                        expected_gain=10,
                    )
                )
            elif category == "domain":
                steps.append(
                    InterviewReadinessRoadmapStep(
                        order=0,
                        title="Подтвердить опыт в предметной области вакансии",
                        expected_gain=8,
                    )
                )
            elif category == "metrics":
                steps.append(
                    InterviewReadinessRoadmapStep(
                        order=0,
                        title="Добавить измеримый результат",
                        expected_gain=6,
                    )
                )

        for question in questions or []:
            answer = question.get("suggested_answer") or {}
            if not isinstance(answer, dict):
                continue

            grounding_status = str(answer.get("grounding_status") or "").strip().lower()
            if grounding_status != "insufficient_evidence":
                continue

            competency = self._roadmap_competency_label(
                question.get("competency_name")
                or question.get("source_requirement")
                or question.get("competency_key")
                or "компетенции"
            )

            steps.append(
                InterviewReadinessRoadmapStep(
                    order=0,
                    title=f"Подготовить подтверждённый пример по теме: {competency}",
                    expected_gain=10,
                )
            )

        steps = sorted(steps, key=lambda item: item.expected_gain, reverse=True)[:5]
        projected_score = min(
            100,
            score + sum(item.expected_gain for item in steps),
        )

        ordered_steps = [
            InterviewReadinessRoadmapStep(
                order=index,
                title=item.title,
                expected_gain=item.expected_gain,
            )
            for index, item in enumerate(steps, start=1)
        ]

        return InterviewReadinessRoadmap(
            current_score=score,
            projected_score=projected_score,
            steps=ordered_steps,
        )

    def _build_readiness_explanation(
        self,
        *,
        score: int,
        weak_areas: list[dict[str, Any]],
        blockers: list[str],
        warnings: list[str],
    ) -> dict[str, Any]:
        def _summary_text() -> str:
            if blockers:
                return "Есть критические пробелы, которые нужно закрыть перед интервью."
            if warnings:
                return "База готовности есть, но остались предупреждения."
            if score >= 80:
                return "Профиль выглядит сильным и готовым к интервью."
            if score >= 60:
                return "Профиль близок к готовности и требует точечной доработки."
            return "Профиль требует заметной доработки перед интервью."

        def _label_for_item(item: dict[str, Any]) -> str:
            return str(
                item.get("competency_label")
                or item.get("source_requirement")
                or item.get("competency_key")
                or item.get("category")
                or "этой зоне"
            ).strip()

        def _next_action_for_item(item: dict[str, Any]) -> str:
            category = str(item.get("category") or "").strip().lower()
            label = _label_for_item(item) or "этой зоне"

            if category == "technical":
                return f"Подтвердить опыт по компетенции: {label}."
            if category == "leadership":
                return "Добавить пример лидерства и влияния на команду."
            if category == "domain":
                return "Подтвердить релевантный опыт в предметной области вакансии."
            if category == "metrics":
                return "Добавить измеримый результат с цифрами."
            return "Проверить доказательства и уточнить факты по этой зоне."

        positive_factors: list[str] = []
        if score >= 60:
            positive_factors.append("Базовый уровень готовности достигнут.")
        if not blockers:
            positive_factors.append("Критических блокеров не найдено.")
        if not warnings:
            positive_factors.append("Предупреждений не найдено.")
        if weak_areas:
            covered_categories = {
                str(item.get("category") or "").strip().lower()
                for item in weak_areas
                if str(item.get("severity") or "").lower() == "warning"
            }
            if "technical" not in covered_categories and score >= 80:
                positive_factors.append("Техническое покрытие выглядит сильным.")

        negative_factors = [
            message
            for message in [*blockers, *warnings]
            if message
        ]

        next_best_actions: list[str] = []
        for item in weak_areas:
            action = _next_action_for_item(item)
            if action not in next_best_actions:
                next_best_actions.append(action)
        if not next_best_actions:
            next_best_actions.append("Сохранять текущий уровень подготовки и повторно проверить readiness позже.")

        return {
            "summary": _summary_text(),
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "next_best_actions": next_best_actions,
        }

    def _roadmap_competency_label(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "компетенции"

        replacements = {
            "коммуникацию": "коммуникация",
            "ответственность": "ответственность",
            "сотрудничество": "сотрудничество",
            "ownership": "ответственность",
            "communication": "коммуникация",
            "collaboration": "сотрудничество",
        }

        normalized = text.lower().replace("_", " ")
        return replacements.get(normalized, text)

    def _matched_required_skill_keys(
        self,
        *,
        competency_map: dict[str, Any],
        confirmed_achievements: list[dict[str, Any]],
        evidence_snippets: list[dict[str, Any]],
    ) -> set[str]:
        matched: set[str] = set()
        vacancy_context_tokens = self._domain_context_tokens(
            competency_map=competency_map,
        )
        for skill in competency_map.get("required_skills") or []:
            skill_text = str(skill["label"])
            skill_tokens = self._tokenize(skill_text)
            for achievement in confirmed_achievements:
                text = achievement_search_text(achievement)
                text_tokens = self._tokenize(text)
                if (
                    skill["key"] in text
                    or skill_tokens & text_tokens
                    or (
                        self._allows_context_only_skill_match(skill_text)
                        and self._has_vacancy_context_match(
                            evidence_text=text,
                            vacancy_context_tokens=vacancy_context_tokens,
                        )
                    )
                    or self._has_domain_cluster_match(
                        skill_label=str(skill.get("label") or ""),
                        evidence_text=text,
                        competency_map=competency_map,
                    )
                ):
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
                    or (
                        self._allows_context_only_skill_match(skill_text)
                        and self._has_vacancy_context_match(
                            evidence_text=text,
                            vacancy_context_tokens=vacancy_context_tokens,
                        )
                    )
                    or self._has_domain_cluster_match(
                        skill_label=str(skill.get("label") or ""),
                        evidence_text=text,
                        competency_map=competency_map,
                    )
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
        domain_expectations: list[str] | None = None,
        *,
        competency_map: dict[str, Any] | None = None,
    ) -> bool:
        if competency_map is None:
            competency_map = {
                "domain_expectations": domain_expectations or [],
            }

        domain_tokens = self._domain_context_tokens(competency_map=competency_map)
        if not domain_tokens:
            return False

        for achievement in achievements:
            text_tokens = self._tokenize(achievement_search_text(achievement))
            if domain_tokens & text_tokens:
                return True

        for evidence in evidence_snippets:
            if not self._is_interview_ready_evidence(evidence):
                continue
            text_tokens = self._tokenize(self._evidence_search_text(evidence))
            if domain_tokens & text_tokens:
                return True

        return False

    def _domain_context_tokens(
        self,
        *,
        competency_map: dict[str, Any],
    ) -> set[str]:
        parts: list[str] = []
        parts.append(str(competency_map.get("vacancy_context_text") or ""))

        for skill in competency_map.get("required_skills") or []:
            parts.append(str(skill.get("label") or ""))
            parts.append(str(skill.get("source_requirement") or ""))

        for item in competency_map.get("domain_requirements") or []:
            parts.append(str(item.get("label") or ""))
            parts.append(str(item.get("source_requirement") or ""))

        for item in competency_map.get("domain_expectations") or []:
            parts.append(str(item or ""))

        raw_tokens = self._tokenize(" ".join(parts))

        stopwords = {
            "и",
            "или",
            "в",
            "во",
            "на",
            "по",
            "для",
            "с",
            "со",
            "к",
            "от",
            "до",
            "при",
            "об",
            "обо",
            "из",
            "за",
            "над",
            "под",
            "а",
            "также",
            "имеете",
            "знаете",
            "умеете",
            "готовы",
            "опыт",
            "работы",
            "работа",
            "образование",
            "высшее",
            "среднее",
            "техническое",
            "экономическое",
            "области",
            "сфере",
            "направлении",
            "части",
            "требования",
            "навыки",
            "знания",
        }

        tokens = {
            token
            for token in raw_tokens
            if token not in stopwords and len(token) >= 4
        }

        synonym_groups = [
            {
                "снабжение",
                "снабжения",
                "закупки",
                "закупок",
                "поставки",
                "поставок",
                "склад",
                "склада",
                "логистика",
                "логистики",
                "мто",
            },
            {
                "договор",
                "договоры",
                "контракт",
                "контракты",
                "документы",
                "документация",
            },
            {
                "бухгалтерия",
                "бухгалтер",
                "учет",
                "учёт",
                "налоги",
                "ндс",
                "первичная",
                "документация",
            },
        ]

        expanded = set(tokens)
        for group in synonym_groups:
            if tokens & group:
                expanded |= group

        return expanded

    def _domain_tokens(self, domain_expectations: list[str]) -> set[str]:
        return self._domain_context_tokens(
            competency_map={
                "domain_expectations": domain_expectations,
            }
        )

    def _has_vacancy_context_match(
        self,
        *,
        evidence_text: str,
        vacancy_context_tokens: set[str],
        min_overlap: int = 2,
    ) -> bool:
        if not vacancy_context_tokens:
            return False

        evidence_tokens = self._tokenize(evidence_text)
        return len(vacancy_context_tokens & evidence_tokens) >= min_overlap

    def _token_stem(self, token: str) -> str:
        text = str(token or "").strip().lower()
        for suffix in (
            "иями", "ями", "ами", "ого", "ему", "ому", "ыми", "ими",
            "ной", "ные", "ная", "ное", "ых", "их",
            "ов", "ев", "ей", "ам", "ям", "ах", "ях",
            "ия", "ие", "ый", "ий", "ая", "ое", "ые",
            "а", "я", "ы", "и", "е", "у", "ю", "ом", "ем",
        ):
            if len(text) > len(suffix) + 3 and text.endswith(suffix):
                return text[: -len(suffix)]
        return text

    def _domain_cluster_tokens(self, text: str) -> set[str]:
        stopwords = {
            "и", "или", "в", "во", "на", "по", "для", "с", "со", "от", "до",
            "при", "об", "из", "за", "работа", "работы", "опыт", "требования",
            "обязанности", "наличие", "знание", "умение", "готовность",
        }
        return {
            self._token_stem(token)
            for token in self._tokenize(text)
            if token not in stopwords and len(token) >= 4
        }

    def _has_domain_cluster_match(
        self,
        *,
        skill_label: str,
        evidence_text: str,
        competency_map: dict[str, Any],
        min_overlap: int = 2,
    ) -> bool:
        context_text = " ".join(
            [
                skill_label,
                str(competency_map.get("vacancy_context_text") or ""),
                " ".join(
                    str(item or "")
                    for item in competency_map.get("domain_expectations") or []
                ),
            ]
        )

        context_tokens = self._domain_cluster_tokens(context_text)
        evidence_tokens = self._domain_cluster_tokens(evidence_text)

        skill_tokens = self._domain_cluster_tokens(skill_label)
        if not (skill_tokens & evidence_tokens) and not self._allows_context_only_skill_match(
            skill_label
        ):
            return False

        return len(context_tokens & evidence_tokens) >= min_overlap

    def _allows_context_only_skill_match(self, skill_label: str) -> bool:
        return any(
            "а" <= char.lower() <= "я" or char.lower() == "ё"
            for char in str(skill_label or "")
        )

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
        vacancy_context_tokens: set[str] | None = None,
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
                or self._has_vacancy_context_match(
                    evidence_text=text,
                    vacancy_context_tokens=vacancy_context_tokens or set(),
                )
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
