# app\services\document_quality_service.py

from __future__ import annotations

import re
from typing import Any

from app.domain.document_quality import DocumentQualityIssue, DocumentQualityReport


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
    def evaluate_resume(
        self,
        *,
        content_json: dict[str, Any],
        rendered_text: str | None = None,
    ) -> DocumentQualityReport:
        sections = content_json.get("sections", {})
        text = rendered_text or ""

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
        )

    def evaluate_cover_letter(
        self,
        *,
        content_json: dict[str, Any],
        rendered_text: str | None = None,
        resume_text: str | None = None,
    ) -> DocumentQualityReport:
        sections = content_json.get("sections", {})
        text = rendered_text or ""

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
        )

    def _score_vacancy_alignment(self, sections: dict[str, Any], *, max_score: int) -> int:
        matched = sections.get("matched_keywords") or []
        missing = sections.get("missing_keywords") or []

        total = len(matched) + len(missing)
        if total == 0:
            return int(max_score * 0.4)

        ratio = len(matched) / total
        return round(max_score * ratio)

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
    ) -> DocumentQualityReport:
        score = max(0, min(100, sum(metrics.values())))
        grade = self._grade(score)

        strengths = self._strengths_from_metrics(metrics)
        improvements = self._improvements_from_issues(issues)
        if score < 70 and not improvements:
            improvements.append(
                "Усилить покрытие требований вакансии и доказательную базу"
            )

        return DocumentQualityReport(
            document_kind=document_kind,
            score=score,
            grade=grade,
            metrics=metrics,
            strengths=strengths,
            improvements=improvements,
            issues=issues,
        )

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
