# app\services\vacancy_fit_narrative_service.py

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from app.domain.evidence_alignment import humanize_experience_phrase
from app.domain.requirement_normalization import (
    classify_requirement_phrase,
    normalize_requirement_phrase,
)


@dataclass(frozen=True)
class VacancyFitItem:
    label: str
    classification: str = "competency"
    evidence: str | None = None
    source: str = "deterministic"


@dataclass(frozen=True)
class VacancyFitNarrative:
    matched_strengths: list[dict[str, Any]]
    transferable_strengths: list[dict[str, Any]]
    critical_gaps: list[dict[str, Any]]
    resume_angle: str
    cover_letter_angle: str


class VacancyFitNarrativeService:
    """
    Builds profession-agnostic fit narrative:
    - direct matches
    - transferable strengths
    - critical gaps

    No LLM, no DB, no profession-specific blocks.
    """

    SOFT_COMPETENCIES = {
        "аккуратность",
        "внимательность",
        "ответственность",
        "исполнительность",
        "коммуникабельность",
    }

    TRANSFERABLE_MARKERS = {
        "management": (
            "управлен",
            "руковод",
            "координац",
            "команд",
            "stakeholder",
            "project management",
        ),
        "communication": (
            "заказчик",
            "клиент",
            "переговор",
            "коммуникац",
            "взаимодейств",
        ),
        "planning": (
            "планирован",
            "срок",
            "бюджет",
            "roadmap",
            "проектн",
        ),
        "quality": (
            "качество",
            "контроль",
            "провер",
            "отчёт",
            "отчет",
            "risk",
            "риск",
        ),
        "documentation": (
            "документац",
            "отчётност",
            "отчетност",
            "confluence",
        ),
    }

    DOMAIN_GAP_MARKERS = (
        "bim",
        "гип",
        "стадии п",
        "стадии р",
        "проектная документация",
        "рабочая документация",
        "revit",
        "autocad",
        "гост",
        "снип",
        "cad",
        "ар",
        "кр",
        "овик",
        "вк",
        "эом",
        "экспертиз",
        "selenium",
        "playwright",
        "kubernetes",
        "jmeter",
    )

    def build(
        self,
        *,
        matched_keywords: list[str],
        missing_keywords: list[str],
        vacancy_evidence_alignment: list[dict[str, Any]],
        selected_achievements: list[dict[str, Any]],
        selected_skills: list[str] | None = None,
    ) -> dict[str, Any]:
        matched_strengths = self._build_matched_strengths(
            vacancy_evidence_alignment=vacancy_evidence_alignment,
        )
        if not matched_strengths:
            matched_strengths = self._build_matched_strengths_from_keywords(
                matched_keywords=matched_keywords,
            )
        transferable_strengths = self._build_transferable_strengths(
            selected_achievements=selected_achievements,
            selected_skills=selected_skills or [],
        )
        critical_gaps = self._build_critical_gaps(missing_keywords=missing_keywords)
        matched_labels = {
            item.label.casefold()
            for item in matched_strengths
        }
        critical_gaps = [
            item
            for item in critical_gaps
            if item.label.casefold() not in matched_labels
        ]

        narrative = VacancyFitNarrative(
            matched_strengths=[asdict(item) for item in matched_strengths],
            transferable_strengths=[asdict(item) for item in transferable_strengths],
            critical_gaps=[asdict(item) for item in critical_gaps],
            resume_angle=self._build_resume_angle(
                matched_strengths=matched_strengths,
                transferable_strengths=transferable_strengths,
                critical_gaps=critical_gaps,
            ),
            cover_letter_angle=self._build_cover_letter_angle(
                matched_strengths=matched_strengths,
                transferable_strengths=transferable_strengths,
                critical_gaps=critical_gaps,
            ),
        )
        return asdict(narrative)

    def _build_matched_strengths(
        self,
        *,
        vacancy_evidence_alignment: list[dict[str, Any]],
    ) -> list[VacancyFitItem]:
        items: list[VacancyFitItem] = []

        for alignment in vacancy_evidence_alignment:
            confidence = str(alignment.get("confidence") or "").lower()
            requirement = self._clean_label(alignment.get("requirement"))
            evidence = self._clean_label(alignment.get("evidence"))

            if not requirement or confidence not in {"high", "medium"}:
                continue

            items.append(
                VacancyFitItem(
                    label=requirement,
                    classification=classify_requirement_phrase(requirement),
                    evidence=evidence or None,
                    source="vacancy_evidence_alignment",
                )
            )

        return self._dedupe_items(items)[:6]

    def _build_matched_strengths_from_keywords(
        self,
        *,
        matched_keywords: list[str],
    ) -> list[VacancyFitItem]:
        items: list[VacancyFitItem] = []

        for keyword in matched_keywords:
            label = self._clean_label(keyword)
            if label:
                items.append(
                    VacancyFitItem(
                        label=label,
                        classification=classify_requirement_phrase(label),
                        source="matched_keyword",
                    )
                )

        return self._dedupe_items(items)[:6]

    def _build_transferable_strengths(
        self,
        *,
        selected_achievements: list[dict[str, Any]],
        selected_skills: list[str],
    ) -> list[VacancyFitItem]:
        corpus_items: list[tuple[str, str]] = []

        for achievement in selected_achievements:
            title = self._clean_label(achievement.get("title"))
            if title:
                corpus_items.append((title, "achievement"))

        for skill in selected_skills:
            cleaned = self._clean_label(skill)
            if cleaned:
                corpus_items.append((cleaned, "skill"))

        items: list[VacancyFitItem] = []
        for text, source in corpus_items:
            lowered = text.lower()
            for group, markers in self.TRANSFERABLE_MARKERS.items():
                if any(marker in lowered for marker in markers):
                    items.append(
                        VacancyFitItem(
                            label=self._humanize_transferable_group(group),
                            classification="competency",
                            evidence=text,
                            source=source,
                        )
                    )

        return self._dedupe_items(items)[:5]

    def _build_critical_gaps(
        self,
        *,
        missing_keywords: list[str],
    ) -> list[VacancyFitItem]:
        items: list[VacancyFitItem] = []

        for keyword in missing_keywords:
            raw_label = self._clean_label(keyword)
            label = self._clean_label(normalize_requirement_phrase(raw_label))
            if not label:
                continue

            if label.lower() in self.SOFT_COMPETENCIES:
                continue

            lowered = f"{raw_label} {label}".lower()
            source = (
                "critical_domain_gap"
                if any(marker in lowered for marker in self.DOMAIN_GAP_MARKERS)
                else "missing_keyword"
            )
            items.append(
                VacancyFitItem(
                    label=label,
                    classification=classify_requirement_phrase(label),
                    source=source,
                )
            )

        return self._dedupe_items(items)[:6]

    def _build_resume_angle(
        self,
        *,
        matched_strengths: list[VacancyFitItem],
        transferable_strengths: list[VacancyFitItem],
        critical_gaps: list[VacancyFitItem],
    ) -> str:
        focus = self._join_labels(
            [item.label for item in [*matched_strengths, *transferable_strengths]][:3]
        )
        if not focus:
            return "Сделать акцент на подтверждённом опыте без добавления неподтверждённых фактов."

        non_soft_gaps = [
            item for item in critical_gaps[:3]
            if item.label.lower() not in self.SOFT_COMPETENCIES
        ]
        if non_soft_gaps:
            gaps = self._join_labels([item.label for item in non_soft_gaps])
            return (
                f"Сделать акцент на подтверждённых совпадениях: {focus}. "
                f"Не заявлять неподтверждённый опыт по зонам: {gaps}."
            )

        return f"Сделать акцент на подтверждённых совпадениях: {focus}."

    def _build_cover_letter_angle(
        self,
        *,
        matched_strengths: list[VacancyFitItem],
        transferable_strengths: list[VacancyFitItem],
        critical_gaps: list[VacancyFitItem],
    ) -> str:
        matched = self._join_labels([item.label for item in matched_strengths[:3]])
        transferable = self._join_labels([item.label for item in transferable_strengths[:2]])

        if matched and transferable:
            return (
                f"В письме связать опыт по направлениям {matched} "
                f"с близкими рабочими задачами: {transferable}."
            )

        if matched:
            return f"В письме кратко подчеркнуть опыт по направлениям: {matched}."

        if transferable:
            return (
                f"В письме показать близкий рабочий опыт: {transferable}, "
                "и готовность быстро разобраться в специфике роли."
            )

        return "В письме использовать спокойную мотивационную формулировку без неподтверждённых фактов."

    def _humanize_transferable_group(self, group: str) -> str:
        mapping = {
            "management": "управление и координация команды",
            "communication": "взаимодействие с заказчиками и стейкхолдерами",
            "planning": "планирование сроков, бюджета и работ",
            "quality": "контроль качества, сроков и рисков",
            "documentation": "ведение документации и отчётности",
        }
        return mapping.get(group, group)

    def _clean_label(self, value: Any) -> str:
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .;-–—•")
        return cleaned

    def _dedupe_items(self, items: list[VacancyFitItem]) -> list[VacancyFitItem]:
        result: list[VacancyFitItem] = []
        seen: set[str] = set()

        for item in items:
            key = item.label.casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)

        return result

    def _join_labels(self, values: list[str]) -> str:
        cleaned = [
            humanize_experience_phrase(cleaned_value)
            for value in values
            if (cleaned_value := self._clean_label(value))
        ]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return " и ".join(cleaned)
        return f"{', '.join(cleaned[:-1])} и {cleaned[-1]}"
