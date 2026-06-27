# app\services\document_quality_service.py

from __future__ import annotations

import re
from typing import Any

from app.services.semantic_requirement_matcher import SemanticRequirementMatcher
from app.domain.document_quality import (
    DocumentQualityIssue,
    ImprovementRoadmap,
    ImprovementRoadmapStep,
    DocumentQualityRecommendation,
    DocumentQualityScoreItem,
    DocumentQualityReport,
)


GENERIC_PHRASES = {
    "готов применять накопленный опыт",
    "ориентирован на результат",
    "ответственность за результат",
    "быстрое включение в процессы",
    "практическая польза команде",
    "буду рад обсудить",
}

LOW_VALUE_SKILLS = {
    "пользователь пк",
    "коммуникабельность",
    "ответственность",
    "исполнительность",
    "аккуратность",
    "внимательность",
}

STRENGTH_LABELS = {
    "vacancy_alignment": "Сильное соответствие требованиям вакансии",
    "evidence_density": "Документ опирается на подтверждённые факты",
    "achievement_quality": "Достижения содержат действия и результаты",
    "ats_quality": "ATS-безопасная структура документа",
    "skills_quality": "Подобраны релевантные профессиональные навыки",
    "summary_quality": "Сильное профессиональное позиционирование",
    "relevance": "Письмо связано с требованиями вакансии",
    "specificity": "Письмо содержит конкретные детали опыта",
    "evidence_usage": "Письмо использует подтверждённые примеры",
    "ai_phrase_density": "Текст звучит достаточно естественно",
    "duplication": "Письмо не дублирует резюме",
}

IMPROVEMENT_LABELS = {
    "low_achievement_density": "Добавить больше достижений с результатами",
    "missing_vacancy_keywords": "Усилить покрытие требований вакансии",
    "keyword_stuffing_risk": "Убрать неестественное повторение ключевых слов",
    "generic_closing": "Сделать финальный абзац более персонализированным",
    "weak_evidence_usage": "Добавить больше подтверждённых примеров опыта",
    "gap_mitigation_present": "Проверить блок про незакрытые требования вручную",
    "resume_letter_duplication": "Снизить повторение резюме в сопроводительном письме",
}


class DocumentQualityService:
    def __init__(
        self,
        semantic_matcher: SemanticRequirementMatcher | None = None,
    ) -> None:
        self.semantic_matcher = semantic_matcher or SemanticRequirementMatcher()

    def evaluate_resume(
        self,
        *,
        content_json: dict[str, Any],
        rendered_text: str | None = None,
    ) -> DocumentQualityReport:
        sections = self._sections_with_quality_context(content_json)
        text = rendered_text or ""
        sections["_rendered_text"] = text

        metrics = {
            "vacancy_alignment": self._score_vacancy_alignment(sections, max_score=25),
            "evidence_density": self._score_evidence_density(sections, max_score=20),
            "achievement_quality": self._score_achievement_quality(sections, max_score=15),
            "ats_quality": self._score_ats_quality(text, max_score=15),
            "skills_quality": self._score_skills_quality(sections, max_score=10),
            "summary_quality": self._score_summary_quality(sections, text, max_score=15),
        }

        return self._build_report(
            document_kind="resume",
            metrics=metrics,
            issues=[
                *self._resume_issues(sections, text),
            ],
            sections=sections,
        )

    def evaluate_cover_letter(
        self,
        *,
        content_json: dict[str, Any],
        rendered_text: str | None = None,
        resume_text: str | None = None,
    ) -> DocumentQualityReport:
        sections = self._sections_with_quality_context(content_json)
        text = rendered_text or ""
        sections["_rendered_text"] = text

        metrics = {
            "relevance": self._score_vacancy_alignment(sections, max_score=30),
            "specificity": self._score_specificity(text, max_score=20),
            "evidence_usage": self._score_evidence_density(sections, max_score=20),
            "ai_phrase_density": self._score_ai_phrase_density(text, max_score=15),
            "duplication": self._score_duplication(text, resume_text, max_score=15),
        }

        return self._build_report(
            document_kind="cover_letter",
            metrics=metrics,
            issues=[
                *self._cover_letter_issues(sections, text, resume_text),
            ],
            sections=sections,
        )

    def _sections_with_quality_context(self, content_json: dict[str, Any]) -> dict[str, Any]:
        sections = dict(content_json.get("sections", {}) or {})
        meta = dict(content_json.get("meta", {}) or {})
        provenance = dict(content_json.get("provenance", {}) or {})

        for key in (
            "selected_evidence_ids",
            "evidence_selection_reason",
            "selected_evidence_reason",
            "vacancy_evidence_alignment",
            "top_alignment_evidence",
        ):
            if sections.get(key):
                continue
            value = meta.get(key)
            if value is None:
                value = provenance.get(key)
            if value:
                sections[key] = value

        if not sections.get("selected_evidence_reason") and sections.get("evidence_selection_reason"):
            sections["selected_evidence_reason"] = sections["evidence_selection_reason"]

        return sections

    def _score_vacancy_alignment(self, sections: dict[str, Any], *, max_score: int) -> int:
        matched = [
            str(item).strip()
            for item in sections.get("matched_keywords") or []
            if str(item).strip()
        ]
        missing = [
            str(item).strip()
            for item in sections.get("missing_keywords") or []
            if str(item).strip()
        ]

        total = len(matched) + len(missing)
        profile_signal_score = self._profile_signal_alignment_baseline(
            sections=sections,
            max_score=max_score,
        )

        if total == 0:
            return profile_signal_score or int(max_score * 0.4)

        semantic_terms = self._semantic_profile_terms(sections)

        semantic_supported = 0
        for keyword in missing:
            if self._formal_requirement_requires_direct_evidence(keyword):
                continue

            match = self.semantic_matcher.match(keyword, semantic_terms)
            if match.matched and match.confidence >= 0.70:
                semantic_supported += 1

        effective_matched = len(matched) + semantic_supported
        ratio = effective_matched / total
        semantic_score = round(max_score * ratio)
        return max(semantic_score, profile_signal_score)

    def _profile_signal_alignment_baseline(
        self,
        *,
        sections: dict[str, Any],
        max_score: int,
    ) -> int:
        skills = [
            str(item).strip()
            for item in sections.get("skills") or []
            if str(item).strip()
        ]
        selected_achievements = [
            item
            for item in sections.get("selected_achievements") or []
            if isinstance(item, dict) and str(item.get("title") or "").strip()
        ]
        evidence_reason = [
            item
            for item in sections.get("evidence_selection_reason")
            or sections.get("selected_evidence_reason")
            or []
            if isinstance(item, dict)
        ]
        top_alignment_evidence = [
            item
            for item in sections.get("top_alignment_evidence") or []
            if isinstance(item, dict)
        ]

        score = 0

        if skills:
            score += 2
        if len(skills) >= 3:
            score += 2
        if selected_achievements:
            score += 2
        if evidence_reason or top_alignment_evidence:
            score += 2

        # Это именно baseline, не полноценное соответствие вакансии.
        # Не даём ему превысить ~40% блока alignment.
        return min(score, int(max_score * 0.4))

    def _score_evidence_density(self, sections: dict[str, Any], *, max_score: int) -> int:
        achievements = sections.get("selected_achievements") or []
        evidence_ids = sections.get("selected_evidence_ids") or []
        evidence_relevance = sections.get("evidence_relevance") or []
        top_alignment = sections.get("top_alignment_evidence") or []

        evidence_count = (
            len(achievements)
            + len(evidence_ids)
            + len(evidence_relevance)
            + len(top_alignment)
        )

        if evidence_count <= 0:
            return 2
        if evidence_count == 1:
            return round(max_score * 0.45)
        if evidence_count == 2:
            return round(max_score * 0.7)
        if evidence_count <= 4:
            return round(max_score * 0.9)
        return max_score

    def _score_achievement_quality(self, sections: dict[str, Any], *, max_score: int) -> int:
        achievements = sections.get("selected_achievements") or []
        if not achievements:
            return 2

        total = 0
        for item in achievements:
            title = str(item.get("title") or "")
            action = str(item.get("action") or "")
            result = str(item.get("result") or "")
            metric = str(item.get("metric_text") or "")

            item_score = 1
            if action or self._has_action_verb(title):
                item_score += 1
            if result:
                item_score += 1
            if metric or self._has_metric(title):
                item_score += 2

            total += min(item_score, 5)

        average = total / max(len(achievements), 1)
        return round(max_score * (average / 5))

    def _score_ats_quality(self, text: str, *, max_score: int) -> int:
        if not text.strip():
            return 0

        score = max_score
        if "|" in text:
            score -= 2
        if "\t" in text:
            score -= 2
        if any(len(line) > 180 for line in text.splitlines()):
            score -= 3
        if self._has_keyword_stuffing(text):
            score -= 4

        return max(score, 0)

    def _score_skills_quality(self, sections: dict[str, Any], *, max_score: int) -> int:
        skills = [
            str(skill).strip()
            for skill in sections.get("skills") or []
            if str(skill).strip()
        ]
        if not skills:
            return 2

        low_value_count = sum(
            1 for skill in skills if skill.casefold() in LOW_VALUE_SKILLS
        )
        low_value_ratio = low_value_count / len(skills)

        score = max_score
        if low_value_ratio >= 0.5:
            score -= 6
        elif low_value_ratio >= 0.25:
            score -= 3

        if len(set(skill.casefold() for skill in skills)) < len(skills):
            score -= 2

        return max(score, 0)

    def _score_summary_quality(
        self,
        sections: dict[str, Any],
        text: str,
        *,
        max_score: int,
    ) -> int:
        summary = str(
            sections.get("vacancy_aligned_summary")
            or sections.get("summary")
            or ""
        )

        if not summary:
            summary = self._first_non_empty_line(text)

        if not summary:
            return 2

        score = max_score
        if self._count_generic_phrases(summary) > 0:
            score -= 4
        if len(summary.split()) < 12:
            score -= 3
        if not self._has_role_or_domain_signal(summary):
            score -= 3

        return max(score, 0)

    def _score_specificity(self, text: str, *, max_score: int) -> int:
        if not text.strip():
            return 0

        score = max_score
        if self._count_generic_phrases(text) >= 2:
            score -= 6
        if not self._has_metric(text) and not self._has_action_verb(text):
            score -= 5
        if len(text.split()) < 80:
            score -= 3

        return max(score, 0)

    def _score_ai_phrase_density(self, text: str, *, max_score: int) -> int:
        count = self._count_generic_phrases(text)
        if count == 0:
            return max_score
        if count == 1:
            return round(max_score * 0.75)
        if count == 2:
            return round(max_score * 0.5)
        return round(max_score * 0.25)

    def _score_duplication(
        self,
        text: str,
        resume_text: str | None,
        *,
        max_score: int,
    ) -> int:
        if not text.strip() or not resume_text:
            return max_score

        letter_tokens = self._content_tokens(text)
        resume_tokens = self._content_tokens(resume_text)

        if not letter_tokens or not resume_tokens:
            return max_score

        overlap = len(letter_tokens & resume_tokens) / len(letter_tokens)

        if overlap >= 0.7:
            return round(max_score * 0.25)
        if overlap >= 0.5:
            return round(max_score * 0.5)
        if overlap >= 0.35:
            return round(max_score * 0.75)
        return max_score

    def _resume_issues(
        self,
        sections: dict[str, Any],
        text: str,
    ) -> list[DocumentQualityIssue]:
        issues: list[DocumentQualityIssue] = []

        if not sections.get("selected_achievements"):
            issues.append(DocumentQualityIssue(
                code="low_achievement_density",
                severity="warning",
                message="В резюме мало выбранных достижений.",
                metric="achievement_quality",
            ))

        if sections.get("missing_keywords"):
            issues.append(DocumentQualityIssue(
                code="missing_vacancy_keywords",
                severity="info",
                message="Часть требований вакансии не закрыта фактами профиля.",
                metric="vacancy_alignment",
            ))

        if self._has_keyword_stuffing(text):
            issues.append(DocumentQualityIssue(
                code="keyword_stuffing_risk",
                severity="warning",
                message="Есть риск неестественного повторения ключевых слов.",
                metric="ats_quality",
            ))

        return issues

    def _cover_letter_issues(
        self,
        sections: dict[str, Any],
        text: str,
        resume_text: str | None,
    ) -> list[DocumentQualityIssue]:
        issues: list[DocumentQualityIssue] = []

        if "готов применять накопленный опыт" in text.casefold():
            issues.append(DocumentQualityIssue(
                code="generic_closing",
                severity="warning",
                message="Финальный абзац звучит механически.",
                metric="ai_phrase_density",
            ))

        if not sections.get("evidence_relevance") and not sections.get("selected_achievements"):
            issues.append(DocumentQualityIssue(
                code="weak_evidence_usage",
                severity="warning",
                message="В письме мало конкретных доказательств релевантности.",
                metric="evidence_usage",
            ))

        if sections.get("missing_keywords"):
            issues.append(DocumentQualityIssue(
                code="gap_mitigation_present",
                severity="info",
                message="Есть незакрытые требования; gap-блок нужно проверить вручную.",
                metric="relevance",
            ))

        if resume_text and self._score_duplication(text, resume_text, max_score=15) < 8:
            issues.append(DocumentQualityIssue(
                code="resume_letter_duplication",
                severity="warning",
                message="Письмо слишком сильно пересекается с резюме.",
                metric="duplication",
            ))

        return issues

    def _build_report(
        self,
        *,
        document_kind: str,
        metrics: dict[str, int],
        issues: list[DocumentQualityIssue],
        sections: dict[str, Any] | None = None,
    ) -> DocumentQualityReport:
        score = max(0, min(100, sum(metrics.values())))
        grade = self._grade(score)

        strengths = self._strengths_from_metrics(metrics)
        improvements = self._improvements_from_issues(issues)
        if score < 70 and not improvements:
            improvements.append(
                "Усилить покрытие требований вакансии и доказательную базу"
            )

        score_breakdown = self._build_score_breakdown(
            document_kind=document_kind,
            metrics=metrics,
        )

        recommendations = self._build_recommendations(
            document_kind=document_kind,
            metrics=metrics,
            issues=issues,
            sections=sections,
        )
        roadmap = self._build_improvement_roadmap(
            score=score,
            recommendations=recommendations,
        )

        return DocumentQualityReport(
            document_kind=document_kind,
            score=score,
            grade=grade,
            metrics=metrics,
            strengths=strengths,
            improvements=improvements,
            issues=issues,
            recommendations=recommendations,
            score_breakdown=score_breakdown,
            roadmap=roadmap,
        )

    def _build_recommendations(
        self,
        *,
        document_kind: str,
        metrics: dict[str, int],
        issues: list[DocumentQualityIssue],
        sections: dict[str, Any],
    ) -> list[DocumentQualityRecommendation]:
        recommendations: list[DocumentQualityRecommendation] = []
        issue_codes = {issue.code for issue in issues}

        if document_kind == "resume":
            recommendations.extend(
                self._resume_recommendations(
                    metrics=metrics,
                    issue_codes=issue_codes,
                    sections=sections,
                )
            )
        elif document_kind == "cover_letter":
            recommendations.extend(
                self._cover_letter_recommendations(
                    metrics=metrics,
                    issue_codes=issue_codes,
                    sections=sections,
                )
            )

        return recommendations[:5]

    def _build_score_breakdown(
        self,
        *,
        document_kind: str,
        metrics: dict[str, int],
    ) -> list[DocumentQualityScoreItem]:
        resume_labels = {
            "vacancy_alignment": ("Соответствие вакансии", 25),
            "evidence_density": ("Доказательная база", 20),
            "achievement_quality": ("Качество достижений", 15),
            "ats_quality": ("ATS качество", 15),
            "skills_quality": ("Навыки", 10),
            "summary_quality": ("Summary", 15),
        }
        cover_letter_labels = {
            "relevance": ("Релевантность вакансии", 30),
            "specificity": ("Конкретика", 20),
            "evidence_usage": ("Использование доказательств", 20),
            "ai_phrase_density": ("Естественность текста", 15),
            "duplication": ("Отсутствие дублирования", 15),
        }

        mapping = (
            resume_labels
            if document_kind == "resume"
            else cover_letter_labels
        )

        return [
            DocumentQualityScoreItem(
                code=code,
                label=label,
                score=metrics.get(code, 0),
                max_score=max_score,
                missing_points=max(max_score - metrics.get(code, 0), 0),
            )
            for code, (label, max_score) in mapping.items()
        ]

    def _recommendation_impact(
        self,
        *,
        metric: str,
        score: int,
        max_score: int,
    ) -> dict[str, Any]:
        return {
            "metric": metric,
            "potential_gain": max(max_score - score, 0),
        }

    def _raw_keyword_alignment_score(self, sections: dict[str, Any], *, max_score: int) -> int:
        matched = [
            str(item).strip()
            for item in sections.get("matched_keywords") or []
            if str(item).strip()
        ]
        missing = [
            str(item).strip()
            for item in sections.get("missing_keywords") or []
            if str(item).strip()
        ]

        total = len(matched) + len(missing)
        if total == 0:
            return int(max_score * 0.4)

        return round(max_score * (len(matched) / total))

    def _build_improvement_roadmap(
        self,
        *,
        score: int,
        recommendations: list[DocumentQualityRecommendation],
    ) -> ImprovementRoadmap | None:
        candidates: list[dict[str, Any]] = []

        for rec in recommendations:
            impact = rec.impact or {}
            gain = int(impact.get("potential_gain") or 0)

            if gain <= 0:
                continue

            candidates.append(
                {
                    "title": rec.title,
                    "gain": gain,
                    "code": rec.code,
                }
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: x["gain"],
            reverse=True,
        )

        steps: list[ImprovementRoadmapStep] = []
        for idx, item in enumerate(candidates[:5], start=1):
            steps.append(
                ImprovementRoadmapStep(
                    order=idx,
                    title=item["title"],
                    expected_gain=item["gain"],
                    recommendation_code=item["code"],
                )
            )

        projected_score = min(
            100,
            score + (steps[0].expected_gain if steps else 0),
        )

        return ImprovementRoadmap(
            current_score=score,
            projected_score=projected_score,
            steps=steps,
        )

    def _resume_recommendations(
        self,
        *,
        metrics: dict[str, int],
        issue_codes: set[str],
        sections: dict[str, Any],
    ) -> list[DocumentQualityRecommendation]:
        recommendations: list[DocumentQualityRecommendation] = []

        missing_keywords = sections.get("missing_keywords") or []
        vacancy_gap_diagnostics = self._vacancy_gap_diagnostics(
            missing_keywords,
            sections=sections,
        )
        missing_count = int(vacancy_gap_diagnostics.get("missing_count") or 0)
        alignment_score = int(metrics.get("vacancy_alignment") or 0)

        if alignment_score < 18 or missing_count > 0:
            raw_alignment_score = self._raw_keyword_alignment_score(
                sections,
                max_score=25,
            )
            rec = DocumentQualityRecommendation(
                code="improve_vacancy_alignment",
                title="Усилить соответствие вакансии",
                why=(
                    "Документ слабо покрывает требования вакансии. "
                    "ATS и рекрутер могут не увидеть прямую связь между опытом и ролью."
                ),
                metric="vacancy_alignment",
                impact=self._recommendation_impact(
                    metric="vacancy_alignment",
                    score=raw_alignment_score,
                    max_score=25,
                ),
            )
            if missing_keywords:
                rec.details = {
                    "vacancy_gap_diagnostics": vacancy_gap_diagnostics
                }
            rec.actions.extend(
                [
                    "Добавить только те навыки и обязанности, которые реально подтверждены профилем.",
                    "Не добавлять неподтверждённый опыт ради совпадения с вакансией.",
                ]
            )
            recommendations.append(rec)

        if metrics.get("achievement_quality", 0) < 10 or "low_achievement_density" in issue_codes:
            diagnostics = self._achievement_diagnostics(sections)
            actions = []
            if diagnostics["total"] == 0:
                actions.append("Добавить 2–3 подтверждённых достижения, связанных с требованиями вакансии.")
            else:
                actions.append(
                    "Диагностика достижений: "
                    f"всего {diagnostics['total']}, "
                    f"без действия {diagnostics['without_action']}, "
                    f"без результата {diagnostics['without_result']}, "
                    f"без метрики {diagnostics['without_metric']}."
                )
            actions.extend(
                [
                    "Для каждого сильного пункта добавить: что сделал, для чего и какой был результат.",
                    "Если есть реальные цифры — добавить метрику.",
                    "Если цифр нет — описать наблюдаемый результат без выдуманных процентов.",
                ]
            )
            recommendations.append(
                DocumentQualityRecommendation(
                    code="improve_achievements",
                    title="Усилить достижения",
                    why=(
                        "В достижениях не хватает действия, результата или измеримого эффекта. "
                        "Из-за этого резюме выглядит как список обязанностей."
                    ),
                    actions=actions,
                    metric="achievement_quality",
                    impact=self._recommendation_impact(
                        metric="achievement_quality",
                        score=metrics.get("achievement_quality", 0),
                        max_score=15,
                    ),
                    details={
                        "achievement_diagnostics": diagnostics,
                    },
                )
            )

        if metrics.get("evidence_density", 0) < 14:
            recommendations.append(
                DocumentQualityRecommendation(
                    code="add_supporting_evidence",
                    title="Добавить доказательную базу",
                    why=(
                        "Документу не хватает подтверждённых фактов из профиля, достижений или evidence bank."
                    ),
                    actions=[
                        "Добавить подтверждённые достижения из профиля.",
                        "Привязать evidence snippets к ключевым требованиям вакансии.",
                        "Пометить спорные утверждения как требующие подтверждения.",
                    ],
                    metric="evidence_density",
                    impact=self._recommendation_impact(
                        metric="evidence_density",
                        score=metrics.get("evidence_density", 0),
                        max_score=20,
                    ),
                )
            )

        if metrics.get("skills_quality", 0) < 8:
            recommendations.append(
                DocumentQualityRecommendation(
                    code="improve_skills_section",
                    title="Почистить навыки",
                    why=(
                        "Секция навыков содержит мало конкретных профессиональных сигналов "
                        "или слишком много общих формулировок."
                    ),
                    actions=[
                        "Оставить профессиональные hard skills и доменные навыки.",
                        "Убрать слабые общие слова вроде «ответственность» и «коммуникабельность», если они не важны для вакансии.",
                        "Сгруппировать похожие навыки без дублей.",
                    ],
                    metric="skills_quality",
                    impact=self._recommendation_impact(
                        metric="skills_quality",
                        score=metrics.get("skills_quality", 0),
                        max_score=10,
                    ),
                )
            )

        return recommendations

    def _cover_letter_recommendations(
        self,
        *,
        metrics: dict[str, int],
        issue_codes: set[str],
        sections: dict[str, Any],
    ) -> list[DocumentQualityRecommendation]:
        recommendations: list[DocumentQualityRecommendation] = []

        if metrics.get("relevance", 0) < 18:
            recommendations.append(
                DocumentQualityRecommendation(
                    code="improve_letter_relevance",
                    title="Сильнее связать письмо с вакансией",
                    why=(
                        "Письмо недостаточно показывает, почему кандидат подходит именно под эту роль."
                    ),
                    actions=[
                        "Назвать 1–2 конкретные задачи вакансии.",
                        "Связать каждую задачу с подтверждённым опытом кандидата.",
                        "Не писать общую мотивацию без связи с требованиями.",
                    ],
                    metric="relevance",
                    impact=self._recommendation_impact(
                        metric="relevance",
                        score=metrics.get("relevance", 0),
                        max_score=30,
                    ),
                )
            )

        if metrics.get("evidence_usage", 0) < 14 or "weak_evidence_usage" in issue_codes:
            recommendations.append(
                DocumentQualityRecommendation(
                    code="add_letter_evidence",
                    title="Добавить конкретный пример опыта",
                    why=(
                        "Письму не хватает факта или достижения, которое подтверждает релевантность кандидата."
                    ),
                    actions=[
                        "Добавить один короткий пример из опыта.",
                        "Использовать только подтверждённые достижения.",
                        "Не повторять резюме дословно.",
                    ],
                    metric="evidence_usage",
                    impact=self._recommendation_impact(
                        metric="evidence_usage",
                        score=metrics.get("evidence_usage", 0),
                        max_score=20,
                    ),
                )
            )

        if "generic_closing" in issue_codes:
            recommendations.append(
                DocumentQualityRecommendation(
                    code="rewrite_generic_closing",
                    title="Переписать финальный абзац",
                    why=(
                        "Финальный абзац звучит шаблонно и снижает ощущение живого письма."
                    ),
                    actions=[
                        "Убрать фразу «готов применять накопленный опыт».",
                        "Закрыть письмо простой фразой о готовности обсудить задачи роли.",
                        "Не добавлять новые неподтверждённые claims в финал.",
                    ],
                    metric="ai_phrase_density",
                    impact=self._recommendation_impact(
                        metric="ai_phrase_density",
                        score=metrics.get("ai_phrase_density", 0),
                        max_score=15,
                    ),
                )
            )

        if "resume_letter_duplication" in issue_codes:
            recommendations.append(
                DocumentQualityRecommendation(
                    code="reduce_resume_duplication",
                    title="Снизить повторение резюме",
                    why=(
                        "Письмо слишком похоже на резюме и не добавляет отдельной ценности."
                    ),
                    actions=[
                        "Оставить в письме только 1–2 самых релевантных аргумента.",
                        "Убрать подробный пересказ опыта.",
                        "Сделать акцент на мотивации и связи с задачами вакансии.",
                    ],
                    metric="duplication",
                    impact=self._recommendation_impact(
                        metric="duplication",
                        score=metrics.get("duplication", 0),
                        max_score=15,
                    ),
                )
            )

        return recommendations

    def _achievement_diagnostics(self, sections: dict[str, Any]) -> dict[str, Any]:
        achievements = [
            item
            for item in (sections.get("selected_achievements") or [])
            if isinstance(item, dict)
        ]

        total = len(achievements)
        without_action = 0
        without_result = 0
        without_metric = 0
        problem_achievements: list[dict[str, Any]] = []

        for item in achievements:
            title = str(
                item.get("title")
                or item.get("name")
                or item.get("text")
                or "Достижение без названия"
            ).strip()

            action = str(item.get("action") or "")
            result = str(item.get("result") or "")
            metric = str(item.get("metric_text") or "")

            missing: list[str] = []

            if not action and not self._has_action_verb(title):
                without_action += 1
                missing.append("action")

            if not result:
                without_result += 1
                missing.append("result")

            if not metric and not self._has_metric(title):
                without_metric += 1
                missing.append("metric")

            if missing:
                severity = self._achievement_problem_severity(missing)
                problem_achievements.append(
                    {
                        "title": title,
                        "missing": missing,
                        "severity": severity,
                        "priority_label": self._achievement_priority_label(severity),
                        "questions": self._achievement_gap_questions(missing),
                        "rewrite_hint": self._achievement_rewrite_hint(
                            title=title,
                            missing=missing,
                        ),
                    }
                )

        problem_achievements.sort(
            key=lambda item: int(item.get("severity") or 0),
            reverse=True,
        )

        return {
            "total": total,
            "without_action": without_action,
            "without_result": without_result,
            "without_metric": without_metric,
            "problem_achievements": problem_achievements[:5],
        }

    def _achievement_gap_questions(self, missing: list[str]) -> list[str]:
        questions: list[str] = []

        if "action" in missing:
            questions.extend(
                [
                    "Что именно вы сделали лично?",
                    "За какой участок работы вы отвечали?",
                ]
            )

        if "result" in missing:
            questions.extend(
                [
                    "Что изменилось после вашей работы?",
                    "Какой результат увидела команда, клиент или бизнес?",
                ]
            )

        if "metric" in missing:
            questions.extend(
                [
                    "Можно ли подтвердить результат числом, сроком, объёмом или процентом?",
                    "Сколько объектов, документов, клиентов, задач или материалов было затронуто?",
                ]
            )

        deduped: list[str] = []
        for question in questions:
            if question not in deduped:
                deduped.append(question)

        return deduped[:6]

    def _achievement_problem_severity(self, missing: list[str]) -> int:
        return min(len(set(missing)), 3)

    def _achievement_priority_label(self, severity: int) -> str:
        if severity >= 3:
            return "Высокий приоритет"
        if severity == 2:
            return "Средний приоритет"
        return "Низкий приоритет"

    def _vacancy_gap_diagnostics(
        self,
        missing_keywords: list[Any],
        sections: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sections = sections or {}

        gaps = [
            self._classify_vacancy_gap(
                str(keyword).strip(),
                sections=sections,
            )
            for keyword in missing_keywords[:10]
            if str(keyword).strip()
        ]

        priority = "high" if len(missing_keywords) >= 5 else "medium"

        return {
            "missing_keywords": [
                gap["keyword"]
                for gap in gaps
            ],
            "missing_count": len(missing_keywords),
            "total_missing": len(missing_keywords),
            "priority": priority,
            "gaps": gaps,
            "actions": [
                "Проверить, есть ли этот навык или обязанность в реальном опыте кандидата",
                "Если опыт подтверждён — добавить конкретный пример",
                "Если опыта нет — не добавлять требование как факт",
            ],
        }

    def _classify_vacancy_gap(
        self,
        keyword: str,
        *,
        sections: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sections = sections or {}
        profile_match = self._gap_profile_match(keyword, sections)

        if profile_match:
            return {
                "keyword": keyword,
                "status": "confirmed_in_profile",
                "label": "Найдено в профиле",
                "safe_to_add": True,
                "importance": self._gap_importance(keyword),
                "coverage_opportunity": self._gap_coverage_opportunity(
                    importance=self._gap_importance(keyword),
                    safe_to_add=True,
                ),
                "reason": (
                    "Требование есть в вакансии и найдено в данных профиля. "
                    "Можно усилить документ, если формулировка не искажает опыт."
                ),
                "matched_sources": profile_match,
            }

        return {
            "keyword": keyword,
            "status": "not_confirmed",
            "label": "Не подтверждено профилем",
            "safe_to_add": False,
            "importance": self._gap_importance(keyword),
            "coverage_opportunity": self._gap_coverage_opportunity(
                importance=self._gap_importance(keyword),
                safe_to_add=False,
            ),
            "reason": (
                "Требование есть в вакансии, но пока не найдено в данных профиля."
            ),
            "matched_sources": [],
        }

    def _gap_importance(self, keyword: str) -> str:
        text = keyword.lower()

        critical_words = [
            "photoshop",
            "coreldraw",
            "excel",
            "1с",
            "sql",
            "python",
            "fastapi",
        ]

        if any(word in text for word in critical_words):
            return "high"

        return "medium"

    def _gap_coverage_opportunity(self, *, importance: str, safe_to_add: bool) -> int:
        if importance == "high" and safe_to_add:
            return 10
        if importance == "medium" and safe_to_add:
            return 5
        if importance == "high":
            return 2
        return 1

    def _gap_profile_match(
        self,
        keyword: str,
        sections: dict[str, Any],
    ) -> list[str]:
        needle = self._normalize_gap_text(keyword)
        if not needle:
            return []

        sources: list[str] = []

        if self._gap_found_in_list(needle, sections.get("skills")):
            sources.append("skills")

        if self._gap_found_in_achievements(needle, sections.get("selected_achievements")):
            sources.append("selected_achievements")

        if self._gap_found_in_list(needle, sections.get("top_alignment_evidence")):
            sources.append("top_alignment_evidence")

        if self._gap_found_in_list(needle, sections.get("matched_keywords")):
            sources.append("matched_keywords")

        return sources

    def _gap_found_in_list(self, needle: str, values: Any) -> bool:
        for value in values or []:
            if needle in self._normalize_gap_text(value):
                return True
        return False

    def _gap_found_in_achievements(self, needle: str, values: Any) -> bool:
        for item in values or []:
            if not isinstance(item, dict):
                continue

            haystack = " ".join(
                str(item.get(field) or "")
                for field in ("title", "action", "result", "metric_text")
            )

            if needle in self._normalize_gap_text(haystack):
                return True

        return False

    def _normalize_gap_text(self, value: Any) -> str:
        return re.sub(
            r"\s+",
            " ",
            str(value or "").casefold().replace("ё", "е"),
        ).strip()

    def _achievement_rewrite_hint(
        self,
        *,
        title: str,
        missing: list[str],
    ) -> str:
        steps: list[str] = [title]

        if "action" in missing:
            steps.append("уточнить личный вклад")

        if "result" in missing:
            steps.append("добавить подтверждённый результат")

        if "metric" in missing:
            steps.append("добавить метрику, если она реально известна")

        return " → ".join(steps)

    def _grade(self, score: int) -> str:
        if score >= 85:
            return "excellent"
        if score >= 70:
            return "good"
        if score >= 55:
            return "needs_work"
        return "weak"

    def _strengths_from_metrics(self, metrics: dict[str, int]) -> list[str]:
        strengths: list[str] = []

        for key, value in metrics.items():
            if value >= self._high_metric_threshold(key):
                strengths.append(STRENGTH_LABELS.get(key, key))

        return strengths

    def _improvements_from_issues(
        self,
        issues: list[DocumentQualityIssue],
    ) -> list[str]:
        improvements: list[str] = []

        for issue in issues:
            if issue.severity not in {"warning", "critical"}:
                continue
            improvements.append(IMPROVEMENT_LABELS.get(issue.code, issue.message))

        return improvements

    def _high_metric_threshold(self, key: str) -> int:
        max_values = {
            "vacancy_alignment": 25,
            "evidence_density": 20,
            "achievement_quality": 15,
            "ats_quality": 15,
            "skills_quality": 10,
            "summary_quality": 15,
            "relevance": 30,
            "specificity": 20,
            "evidence_usage": 20,
            "ai_phrase_density": 15,
            "duplication": 15,
        }
        return round(max_values.get(key, 10) * 0.8)

    def _count_generic_phrases(self, text: str) -> int:
        normalized = text.casefold()
        return sum(1 for phrase in GENERIC_PHRASES if phrase in normalized)

    def _has_metric(self, text: str) -> bool:
        return bool(re.search(r"\d+\s*(%|процент|раз|руб|₽|тыс|млн|дн|час)", text.casefold()))

    def _has_action_verb(self, text: str) -> bool:
        return bool(re.search(
            r"\b(сократил|сократила|увеличил|увеличила|снизил|снизила|"
            r"разработал|разработала|внедрил|внедрила|организовал|организовала|"
            r"подготовил|подготовила|настроил|настроила|оптимизировал|оптимизировала)\b",
            text.casefold(),
        ))

    def _has_keyword_stuffing(self, text: str) -> bool:
        tokens = self._content_tokens(text)
        if len(tokens) < 20:
            return False

        words = [
            token
            for token in re.split(r"[^a-zа-яё0-9]+", text.casefold())
            if len(token) >= 5
        ]
        if not words:
            return False

        frequencies = {
            word: words.count(word)
            for word in set(words)
        }
        return any(count >= 8 for count in frequencies.values())

    def _has_role_or_domain_signal(self, text: str) -> bool:
        return bool(re.search(
            r"(бухгалтер|юрист|врач|дизайн|снабжен|закуп|python|backend|project|manager|сантехник)",
            text.casefold(),
        ))

    def _first_non_empty_line(self, text: str) -> str:
        for line in text.splitlines():
            if line.strip():
                return line.strip()
        return ""

    def _content_tokens(self, text: str) -> set[str]:
        stopwords = {
            "для", "или", "это", "как", "что", "при", "над", "под", "без",
            "the", "and", "for", "with", "from", "this", "that",
        }
        return {
            token
            for token in re.split(r"[^a-zа-яё0-9]+", text.casefold())
            if len(token) >= 4 and token not in stopwords
        }

    def _semantic_profile_terms(self, sections: dict[str, Any]) -> list[str]:
        terms: list[str] = []

        rendered_text = str(sections.get("_rendered_text") or "").strip()
        if rendered_text:
            terms.append(rendered_text)

        for key in (
            "skills",
            "matched_keywords",
            "top_alignment_evidence",
            "evidence_relevance",
            "selected_evidence_reason",
        ):
            values = sections.get(key) or []
            for item in values:
                if isinstance(item, str):
                    terms.append(item)
                elif isinstance(item, dict):
                    for field in (
                        "title",
                        "label",
                        "keyword",
                        "reason",
                        "evidence",
                        "snippet_text",
                        "requirement",
                    ):
                        value = str(item.get(field) or "").strip()
                        if value:
                            terms.append(value)

                    for skill in item.get("skills") or []:
                        if str(skill).strip():
                            terms.append(str(skill).strip())

        for achievement in sections.get("selected_achievements") or []:
            if not isinstance(achievement, dict):
                continue
            for field in (
                "title",
                "situation",
                "task",
                "action",
                "result",
                "metric_text",
            ):
                value = str(achievement.get(field) or "").strip()
                if value:
                    terms.append(value)

        return self._dedupe_text_terms(terms)

    def _dedupe_text_terms(self, values: list[str]) -> list[str]:
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

    def _formal_requirement_requires_direct_evidence(self, value: str) -> bool:
        lowered = str(value or "").casefold().replace("ё", "е")
        return any(
            marker in lowered
            for marker in (
                "диплом",
                "образование",
                "сертификат",
                "сертификация",
                "аккредитация",
                "лицензия",
                "удостоверение",
                "допуск",
            )
        )
