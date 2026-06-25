# app/services/interview_answer_synthesis_service.py

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from app.services.interview_answer_quality_service import (
    InterviewAnswerQualityService,
)


class InterviewAnswerSynthesisService:
    """Build deterministic interview answer drafts from STAR evidence."""

    def attach_suggested_answers(
        self,
        *,
        questions: list[dict[str, Any]],
        evidence_snippets: Sequence[Mapping[str, Any]],
        confirmed_achievements: Sequence[Mapping[str, Any]] | None = None,
        weak_areas: Sequence[Mapping[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        evidence_by_id: dict[str, dict[str, Any]] = {}
        for item in confirmed_achievements or []:
            evidence_id = str(
                item.get("id") or item.get("achievement_id") or ""
            ).strip()
            if evidence_id:
                evidence_by_id[evidence_id] = self._normalize_evidence(item)

        for item in evidence_snippets:
            evidence_id = str(
                item.get("id") or item.get("achievement_id") or ""
            ).strip()
            if evidence_id:
                evidence_by_id[evidence_id] = self._normalize_evidence(item)

        weak_area_by_key = {
            str(item.get("competency_key") or "").strip(): dict(item)
            for item in (weak_areas or [])
            if str(item.get("competency_key") or "").strip()
        }

        enriched: list[dict[str, Any]] = []
        for question in questions:
            item = dict(question)
            item["suggested_answer"] = self.build_answer(
                question=item,
                evidence_by_id=evidence_by_id,
                weak_area=weak_area_by_key.get(
                    str(item.get("competency_key") or "").strip()
                ),
            )
            enriched.append(item)

        return enriched

    def _normalize_evidence(
        self,
        evidence: Mapping[str, Any],
    ) -> dict[str, Any]:
        item = dict(evidence)
        if not item.get("star_summary"):
            item["star_summary"] = {
                field: item.get(field)
                for field in ("situation", "task", "action", "result")
                if str(item.get(field) or "").strip()
            }
        if not item.get("snippet_text"):
            item["snippet_text"] = " ".join(
                str(item.get(field) or "").strip()
                for field in ("title", "situation", "task", "action", "result")
                if str(item.get(field) or "").strip()
            )
        return item

    def build_answer(
        self,
        *,
        question: Mapping[str, Any],
        evidence_by_id: Mapping[str, Mapping[str, Any]],
        weak_area: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence = self._select_question_evidence(question, evidence_by_id)
        category = str(question.get("category") or "").strip().lower()

        if category == "gap-risk":
            return self._build_gap_answer(question=question, weak_area=weak_area)

        grounding_status = self._answer_grounding_status(evidence)
        can_build_star = grounding_status == "grounded"

        star = self._resolve_star(evidence) if can_build_star else {}
        skills = self._resolve_skills(evidence)
        competency = self._normalize_competency_label(
            question.get("competency_name")
            or question.get("source_requirement")
            or question.get("competency_key")
            or ""
        )

        answer = {
            "format": "STAR_plus_tradeoffs",
            "situation": (
                star.get("situation")
                if can_build_star
                else self._ungrounded_situation(
                    evidence=evidence,
                    grounding_status=grounding_status,
                )
            ),
            "task": (
                star.get("task")
                if can_build_star
                else self._ungrounded_task(
                    competency=competency,
                    grounding_status=grounding_status,
                )
            ),
            "action": (
                star.get("action")
                if can_build_star
                else self._ungrounded_action(
                    grounding_status=grounding_status,
                )
            ),
            "result": (
                star.get("result")
                if can_build_star
                else self._ungrounded_result(
                    grounding_status=grounding_status,
                )
            ),
            "tech_stack": skills[:8],
            "tradeoffs": self._build_tradeoffs(
                question=question,
                evidence=evidence,
                skills=skills,
            ),
            "talking_points": self._build_talking_points(
                evidence=evidence,
                skills=skills,
                competency=competency,
            ),
            "source_evidence_id": str(evidence.get("id") or evidence.get("achievement_id") or "").strip()
            or None,
            "source_title": str(evidence.get("title") or "").strip() or None,
            "fact_status": str(evidence.get("fact_status") or "needs_review"),
            "grounding_status": grounding_status,
            "requires_human_review": True,
        }
        answer["draft_text"] = self._render_draft_text(answer)
        answer["quality"] = InterviewAnswerQualityService().evaluate(answer).as_dict()
        return answer

    def _select_question_evidence(
        self,
        question: Mapping[str, Any],
        evidence_by_id: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        for evidence_id in question.get("recommended_evidence_ids") or []:
            item = evidence_by_id.get(str(evidence_id))
            if item:
                return dict(item)

        source_id = str(question.get("source_achievement_id") or "").strip()
        if source_id and source_id in evidence_by_id:
            return dict(evidence_by_id[source_id])

        return {}

    def _requires_ownership_review(self, evidence: Mapping[str, Any]) -> bool:
        fact_status = str(evidence.get("fact_status") or "").strip().lower()
        ownership_confidence = str(
            evidence.get("ownership_confidence")
            or evidence.get("candidate_ownership_confidence")
            or ""
        ).strip().lower()
        return (
            bool(evidence.get("requires_confirmation") is True)
            or ownership_confidence in {"low", "unknown", "needs_review"}
            or fact_status in {"needs_confirmation", "unverified", "partial"}
        )

    def _resolve_star(self, evidence: Mapping[str, Any]) -> dict[str, str]:
        star = dict(evidence.get("star_summary") or {})
        result: dict[str, str] = {}

        for key in ("situation", "task", "action", "result"):
            value = self._sanitize_answer_text(star.get(key))
            if value:
                result[key] = value

        return result

    def _can_build_grounded_star(self, evidence: Mapping[str, Any]) -> bool:
        if not evidence:
            return False

        if self._requires_ownership_review(evidence):
            return False

        fact_status = str(evidence.get("fact_status") or "").strip().lower()
        if fact_status not in {"confirmed", "user_provided"}:
            return False

        raw_star = dict(evidence.get("star_summary") or {})
        star = self._resolve_star(evidence)
        if not (star.get("action") and star.get("result")):
            return False

        blocked_fragments = [
            "extracted as a normalized contribution signal",
            "candidate ownership must be reviewed",
            "implementation signal",
            "workflow automation signal",
        ]
        for key in ("situation", "task", "action", "result"):
            raw_text = str(raw_star.get(key) or "").strip().lower()
            if raw_text and any(fragment in raw_text for fragment in blocked_fragments):
                return False

        return True

    def _answer_grounding_status(self, evidence: Mapping[str, Any]) -> str:
        if not evidence:
            return "insufficient_evidence"

        if self._requires_ownership_review(evidence):
            return "needs_confirmation"

        star = self._resolve_star(evidence)
        if star.get("action") and star.get("result"):
            return "grounded"

        return "partial_evidence"

    def _sanitize_answer_text(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        blocked_fragments = [
            "extracted as a normalized contribution signal",
            "candidate ownership must be reviewed",
            "implementation signal",
            "workflow automation signal",
        ]

        lowered = text.lower()
        for fragment in blocked_fragments:
            if fragment in lowered:
                text = text[: lowered.find(fragment)].strip(" .;:-")
                break

        return text

    def _resolve_skills(self, evidence: Mapping[str, Any]) -> list[str]:
        skills = [
            self._normalize_skill(str(skill))
            for skill in (evidence.get("skills") or [])
            if str(skill).strip()
        ]
        text = " ".join(
            [
                str(evidence.get("title") or ""),
                str(evidence.get("snippet_text") or ""),
                " ".join(skills),
            ]
        ).lower()
        inferred = [
            ("FastAPI", r"\bfastapi\b"),
            ("Python", r"\bpython\b"),
            ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
            ("SQLAlchemy", r"\bsqlalchemy\b"),
            ("OpenAI", r"\bopenai\b"),
            ("AI Workflow", r"\bai workflow\b|\bworkflow\b|\borchestrat"),
            ("Docker", r"\bdocker\b"),
            ("Pytest", r"\bpytest\b|\btesting\b"),
        ]
        for label, pattern in inferred:
            if re.search(pattern, text, flags=re.IGNORECASE):
                skills.append(label)
        return [
            skill
            for skill in self._dedupe(skills)
            if self._is_technical_skill(skill)
        ]

    def _is_technical_skill(self, value: str) -> bool:
        text = value.strip().lower()
        if not text:
            return False

        behavioral = {
            "leadership",
            "ownership",
            "communication",
            "collaboration",
            "mentoring",
            "stakeholder",
            "stakeholder management",
            "teamwork",
            "learning agility",
        }
        if text in behavioral:
            return False

        return True

    def _build_gap_answer(
        self,
        *,
        question: Mapping[str, Any],
        weak_area: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        competency = self._normalize_competency_label(
            question.get("competency_name")
            or question.get("competency_key")
            or "этой зоне"
        )
        message = str((weak_area or {}).get("message") or "").strip()
        limitation = self._humanize_gap_message(message) or f"нет сильного подтверждённого опыта по {competency}"
        answer = {
            "format": "honest_gap_response",
            "situation": f"По {competency} важно ответить честно и без преувеличений.",
            "task": f"Показать понимание требования и план закрытия пробела: {limitation}.",
            "action": (
                "Я бы прямо обозначил текущий уровень, связал его с ближайшим "
                "подтверждённым опытом и предложил конкретный план добора практики."
            ),
            "result": (
                "Такой ответ снижает риск неподтверждённых утверждений и показывает зрелый подход к обучению."
            ),
            "tech_stack": [],
            "tradeoffs": [
                "Не заявлять опыт, который не подтверждён фактами",
                "Показать ближайший релевантный опыт и понятный план закрытия пробела",
            ],
            "talking_points": [
                f"Честно обозначить текущий уровень по теме: {competency}",
                "Связать ответ с подтверждённым смежным опытом",
                "Назвать 2–3 конкретных шага, как быстро закрыть пробел перед выходом на роль",
            ],
            "source_evidence_id": None,
            "source_title": None,
            "fact_status": "inferred_needs_review",
            "requires_human_review": True,
        }
        answer["draft_text"] = self._render_draft_text(answer)
        answer["quality"] = InterviewAnswerQualityService().evaluate(answer).as_dict()
        return answer

    def _humanize_gap_message(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        match = re.fullmatch(r"No confirmed (.+) evidence\.?", text, flags=re.IGNORECASE)
        if match:
            return f"нет подтверждённых доказательств по теме {self._normalize_competency_label(match.group(1))}"

        return text

    def _ungrounded_situation(
        self,
        *,
        evidence: Mapping[str, Any],
        grounding_status: str,
    ) -> str:
        title = str(evidence.get("title") or "").strip()
        if grounding_status == "partial_evidence":
            if title:
                return f"Есть релевантный факт: {title}."
            return "Пока есть релевантный факт, но STAR-история ещё не полная."
        if grounding_status == "needs_confirmation":
            if title:
                return f"Найден возможный пример, но его нужно подтвердить: {title}."
            return "Найден возможный пример, но его нужно подтвердить."
        return "Пока нет достаточно подтверждённого примера для безопасного STAR-ответа."

    def _ungrounded_task(
        self,
        *,
        competency: str,
        grounding_status: str,
    ) -> str:
        if grounding_status == "partial_evidence":
            return (
                f"Дособрать задачу, личный вклад и результат по теме "
                f"{competency or 'вопроса'}."
            )

        if grounding_status == "needs_confirmation":
            return (
                f"Проверить, можно ли безопасно использовать этот пример "
                f"для темы {competency or 'вопроса'}."
            )

        return f"Подготовить реальный пример по теме {competency or 'вопроса'}."

    def _ungrounded_action(self, *, grounding_status: str) -> str:
        if grounding_status == "partial_evidence":
            return "Уточнить, что именно вы сделали лично."

        if grounding_status == "needs_confirmation":
            return "Подтвердить личный вклад перед использованием примера."

        return "Не добавлять неподтверждённые действия или личный вклад."

    def _ungrounded_result(self, *, grounding_status: str) -> str:
        if grounding_status == "partial_evidence":
            return "Добавить проверяемый результат или метрику, если она реально известна."

        if grounding_status == "needs_confirmation":
            return "Использовать только подтверждённый результат."

        return "Добавить подтверждённый результат, если он реально известен."

    def _fallback_situation(
        self,
        *,
        evidence: Mapping[str, Any],
        competency: str,
    ) -> str:
        title = str(evidence.get("title") or "").strip()
        if title:
            return f"В проекте {title} нужно было показать практический опыт по {competency or 'ключевой компетенции'}."
        return f"Нужно было привести проверяемый пример по {competency or 'ключевой компетенции'}."

    def _fallback_task(
        self,
        *,
        evidence: Mapping[str, Any],
        competency: str,
    ) -> str:
        skills = self._resolve_skills(evidence)
        if skills:
            return f"Сформулировать задачу через стек и вклад: {', '.join(skills[:4])}."
        return f"Объяснить задачу, ограничения и личный вклад по теме {competency or 'вопроса'}."

    def _fallback_action(
        self,
        *,
        evidence: Mapping[str, Any],
        competency: str,
    ) -> str:
        text = str(evidence.get("snippet_text") or "").strip()
        if text:
            return self._clean_sentence(text)
        if "fastapi" in competency.lower():
            return (
                "Можно описать пример backend/API через подтверждённые действия, "
                "границы endpoint-ов, слой хранения данных и логику workflow — без добавления "
                "непроверенных утверждений."
            )
        return "Описать решение через конкретные шаги реализации и проверяемые доказательства."

    def _fallback_result(self, *, evidence: Mapping[str, Any]) -> str:
        title = str(evidence.get("title") or "").strip()
        if title:
            return f"Получился подтверждаемый пример для интервью: {title}."
        return "Получился структурированный STAR-ответ, который нужно проверить перед интервью."

    def _build_tradeoffs(
        self,
        *,
        question: Mapping[str, Any],
        evidence: Mapping[str, Any],
        skills: list[str],
    ) -> list[str]:
        text = " ".join(
            [
                str(question.get("prompt") or ""),
                str(evidence.get("title") or ""),
                str(evidence.get("snippet_text") or ""),
                " ".join(skills),
            ]
        ).lower()
        tradeoffs: list[str] = []
        if "fastapi" in text or "backend" in text:
            tradeoffs.append("Разделить API-слой, бизнес-процесс и границы хранения данных")
        if "postgres" in text or "sqlalchemy" in text:
            tradeoffs.append("Балансировать простоту модели данных и возможность расширения")
        if "workflow" in text or "openai" in text or "llm" in text:
            tradeoffs.append("Сохранять детерминированную проверку вокруг результата AI")
        if "testing" in text or "pytest" in text:
            tradeoffs.append("Покрывать критичные ветки тестами вместо проверки только успешного сценария")
        return tradeoffs or ["Держать ответ привязанным к подтверждённым фактам без лишних утверждений"]

    def _build_talking_points(
        self,
        *,
        evidence: Mapping[str, Any],
        skills: list[str],
        competency: str,
    ) -> list[str]:
        points: list[str] = []
        if competency:
            points.append(
                f"Начать с связи ответа с компетенцией: {self._normalize_competency_label(competency)}"
            )
        if evidence.get("title"):
            points.append(f"Назвать проект/факт: {evidence.get('title')}")
        if skills:
            points.append(f"Упомянуть стек: {', '.join(skills[:5])}")
        points.append("Закрыть ответ результатом и тем, какие факты были проверены")
        return points

    def _render_draft_text(self, answer: Mapping[str, Any]) -> str:
        lines = [
            f"Ситуация: {answer.get('situation')}",
            f"Задача: {answer.get('task')}",
            f"Действия: {answer.get('action')}",
            f"Результат: {answer.get('result')}",
        ]
        tech_stack = answer.get("tech_stack") or []
        if tech_stack:
            lines.append(f"Стек: {', '.join(str(item) for item in tech_stack)}")
        tradeoffs = answer.get("tradeoffs") or []
        if tradeoffs:
            lines.append(
                "Компромиссы: " + "; ".join(str(item) for item in tradeoffs[:3])
            )
        return "\n".join(line for line in lines if line and not line.endswith(": None"))

    def _normalize_skill(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value).strip(" .;-–—•")
        known = {
            "llm": "LLM",
            "ai": "AI",
            "openai": "OpenAI",
            "chatgpt": "ChatGPT",
            "python": "Python",
            "fastapi": "FastAPI",
            "sqlalchemy": "SQLAlchemy",
            "postgresql": "PostgreSQL",
            "ai workflow": "AI Workflow",
        }
        return known.get(cleaned.lower(), cleaned)

    def _normalize_competency_label(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        replacements = {
            "коммуникацию": "коммуникация",
            "коммуникацией": "коммуникация",
            "компетенцией: коммуникацию": "компетенцией: коммуникация",
            "теме коммуникацию": "теме коммуникация",
        }
        normalized = replacements.get(text.lower(), text)
        if text[:1].isupper() and normalized:
            return normalized[:1].upper() + normalized[1:]
        return normalized

    def _clean_sentence(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip(" .;-–—•")

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = self._clean_sentence(str(value))
            key = cleaned.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result
