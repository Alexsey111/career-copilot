# app\services\interview_preparation_service.py

from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interview_models import (
    InterviewFeedbackDraft,
    InterviewQuestionDraft,
    InterviewScoreDraft,
)
from app.repositories.candidate_profile_repository import CandidateProfileRepository
from app.repositories.interview_session_repository import InterviewSessionRepository
from app.repositories.vacancy_analysis_repository import VacancyAnalysisRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.schemas.json_contracts import InterviewSessionSchema
from app.services.answer_evaluation_engine import AnswerEvaluationEngine
from app.services.interview_serialization import (
    serialize_feedback,
    serialize_question,
    serialize_score,
)


class InterviewPreparationService:
    def __init__(
        self,
        interview_session_repository: InterviewSessionRepository | None = None,
        vacancy_repository: VacancyRepository | None = None,
        vacancy_analysis_repository: VacancyAnalysisRepository | None = None,
        candidate_profile_repository: CandidateProfileRepository | None = None,
        ai_orchestrator: Any | None = None,
    ) -> None:
        self.interview_session_repository = (
            interview_session_repository or InterviewSessionRepository()
        )
        self.vacancy_repository = vacancy_repository or VacancyRepository()
        self.vacancy_analysis_repository = (
            vacancy_analysis_repository or VacancyAnalysisRepository()
        )
        self.candidate_profile_repository = (
            candidate_profile_repository or CandidateProfileRepository()
        )
        self.ai_orchestrator = ai_orchestrator

    async def create_session(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        vacancy_id: UUID,
        session_type: str,
    ):
        vacancy = await self.vacancy_repository.get_by_id(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if vacancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="vacancy not found",
            )

        analysis = await self.vacancy_analysis_repository.get_latest_for_vacancy(
            session,
            vacancy_id,
            user_id=user_id,
        )
        if analysis is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="vacancy analysis not found; run vacancy analysis first",
            )

        profile = await self.candidate_profile_repository.get_with_related_by_user_id(
            session,
            user_id,
        )
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="candidate profile not found; run profile extraction first",
            )

        question_set = self._build_question_set(
            vacancy_title=vacancy.title,
            company=vacancy.company,
            must_have=analysis.must_have_json,
            nice_to_have=analysis.nice_to_have_json,
            strengths=analysis.strengths_json,
            gaps=analysis.gaps_json,
            achievements=[
                {
                    "title": item.title,
                    "fact_status": item.fact_status,
                }
                for item in profile.achievements
            ],
        )

        validated = InterviewSessionSchema(question_set=question_set)
        question_set = [q.model_dump() for q in validated.question_set]

        interview_session = await self.interview_session_repository.create(
            session,
            user_id=user_id,
            vacancy_id=vacancy.id,
            session_type=session_type.strip().lower() or "vacancy",
            status="draft",
            question_set_json=question_set,
            answers_json=[],
            feedback_json={},
            score_json={},
        )

        await session.commit()
        await session.refresh(interview_session)
        return interview_session

    async def get_session(
        self,
        session: AsyncSession,
        *,
        session_id: UUID,
        user_id: UUID,
    ):
        interview_session = await self.interview_session_repository.get_by_id(
            session,
            session_id,
            user_id=user_id,
        )
        if interview_session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="interview session not found",
            )

        return interview_session

    async def list_session_dashboard_items(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> list[dict]:
        return await self.interview_session_repository.list_dashboard_by_user_id(
            session,
            user_id,
        )

    def get_question_by_id(self, *, question_set: list[dict], question_id: str) -> dict:
        question = next(
            (
                item
                for item in question_set
                if item.get("question_id") == question_id
            ),
            None,
        )
        if question is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="question_id not found in interview session",
            )
        return question

    async def build_competency_detail(
        self,
        session: AsyncSession,
        *,
        interview_session,
        competency_key: str,
    ) -> dict[str, Any]:
        question_set = interview_session.question_set_json or []
        answers = interview_session.answers_json or []
        feedback_items = (interview_session.feedback_json or {}).get("items") or []
        competency_readiness = (
            (interview_session.score_json or {}).get("competency_readiness") or []
        )

        questions = [
            question
            for question in question_set
            if question.get("competency_key") == competency_key
        ]
        question_ids = [
            str(question.get("question_id"))
            for question in questions
            if question.get("question_id")
        ]

        filtered_answers = [
            answer
            for answer in answers
            if answer.get("question_id") in question_ids
        ]
        filtered_feedback_items = [
            item
            for item in feedback_items
            if item.get("question_id") in question_ids
        ]
        attempts = await self.interview_session_repository.list_attempts_by_question_ids(
            session,
            session_id=interview_session.id,
            question_ids=question_ids,
        )

        competency = next(
            (
                item
                for item in competency_readiness
                if item.get("competency_key") == competency_key
            ),
            None,
        )
        if competency is None:
            first_question = questions[0] if questions else {}
            competency = {
                "competency_key": competency_key,
                "competency_name": first_question.get("competency_name")
                or first_question.get("requirement_text")
                or competency_key,
            }

        return {
            "competency": competency,
            "questions": questions,
            "answers": filtered_answers,
            "feedback_items": filtered_feedback_items,
            "attempts": [
                {
                    "id": str(attempt.id),
                    "question_id": attempt.question_id,
                    "answer_text": attempt.answer_text,
                    "score": attempt.score,
                    "feedback_json": attempt.feedback_json,
                    "created_at": attempt.created_at.isoformat(),
                }
                for attempt in attempts
            ],
        }

    async def save_answers(
        self,
        session: AsyncSession,
        *,
        session_id: UUID,
        user_id: UUID,
        answers: list[dict],
    ):
        interview_session = await self.get_session(
            session,
            session_id=session_id,
            user_id=user_id,
        )

        normalized_answers = self._validate_and_normalize_answers(
            question_set=interview_session.question_set_json,
            answers=answers,
        )
        feedback_json = self._build_feedback(
            question_set=interview_session.question_set_json,
            answers=normalized_answers,
        )
        score_json = self._build_score(
            feedback_json,
            question_set=interview_session.question_set_json,
        )

        validated = InterviewSessionSchema(
            answers=normalized_answers,
            feedback=feedback_json,
            score=score_json,
        )

        interview_session = await self.interview_session_repository.save_answers(
            session,
            interview_session,
            answers_json=[a.model_dump() for a in validated.answers],
            feedback_json=validated.feedback,
            score_json=validated.score.model_dump(),
            status="answered",
        )

        await session.commit()
        await session.refresh(interview_session)
        return interview_session

    def _validate_and_normalize_answers(
        self,
        *,
        question_set: list[dict],
        answers: list[dict],
    ) -> list[dict]:
        max_index = len(question_set) - 1
        seen_indexes: set[int] = set()
        normalized: list[dict] = []

        for item in answers:
            question_index = int(item["question_index"])

            if question_index < 0 or question_index > max_index:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"question_index out of range: {question_index}",
                )

            if question_index in seen_indexes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"duplicate answer for question_index: {question_index}",
                )

            seen_indexes.add(question_index)
            question = question_set[question_index]
            expected_question_id = str(question.get("question_id") or "").strip()
            provided_question_id = str(item["question_id"]).strip()

            if not expected_question_id or provided_question_id != expected_question_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "question_id does not match question_index: "
                        f"{question_index}"
                    ),
                )

            answer_text = str(item.get("answer_text", "")).strip()

            normalized.append(
                {
                    "question_id": expected_question_id,
                    "question_index": question_index,
                    "question_type": question.get("type"),
                    "answer_format": question.get("answer_format"),
                    "answer_text": answer_text,
                }
            )

        return normalized

    def _build_feedback(
        self,
        *,
        question_set: list[dict],
        answers: list[dict],
    ) -> dict:
        items: list[dict] = []

        for answer in answers:
            question_index = answer["question_index"]
            question = question_set[question_index]
            answer_text = answer["answer_text"]
            answer_lower = answer_text.lower()

            warnings: list[str] = []
            suggestions: list[str] = []

            if not answer_text:
                warnings.append("empty_answer")
                suggestions.append(
                    "Добавьте конкретный ответ перед использованием в подготовке к интервью."
                )
            else:
                if question.get("answer_format") in {"STAR", "STAR_or_example"}:
                    star_markers = self._count_star_markers(answer_lower)
                    if star_markers < 2:
                        warnings.append("weak_star_structure")
                        suggestions.append(
                            "Усильте ответ по структуре STAR: ситуация, задача, действия, результат."
                        )

                if question.get("type") == "gap_preparation":
                    risky_phrases = self._find_overclaim_phrases(answer_lower)
                    if risky_phrases:
                        warnings.append("possible_gap_overclaim")
                        suggestions.append(
                            "Это ответ по gap-зоне. Не представляйте слабый или отсутствующий опыт "
                            "как подтверждённую экспертизу."
                        )

                if self._contains_unverified_metric(answer_text):
                    warnings.append("metric_needs_confirmation")
                    suggestions.append(
                        "Подтвердите метрику перед тем, как использовать её как сильное утверждение."
                    )

            items.append(
                {
                    "question_id": question.get("question_id"),
                    "question_index": question_index,
                    "question_type": question.get("type"),
                    "warnings": warnings,
                    "suggestions": suggestions,
                    "answer_length": len(answer_text),
                }
            )

        feedback_draft = InterviewFeedbackDraft()
        serialized_feedback = serialize_feedback(feedback_draft)
        serialized_feedback["feedback_version"] = "deterministic_v1"
        serialized_feedback["items"] = items

        validated = InterviewSessionSchema(feedback=serialized_feedback)
        return validated.feedback

    def _build_score(
        self,
        feedback_json: dict,
        *,
        question_set: list[dict],
    ) -> dict:
        items = feedback_json.get("items", [])
        answered_count = sum(1 for item in items if item.get("answer_length", 0) > 0)
        warning_count = sum(len(item.get("warnings", [])) for item in items)
        question_count = len(question_set)
        unanswered_count = max(0, question_count - answered_count)

        if question_count == 0:
            readiness_score = None
        else:
            readiness_score = self._calculate_readiness_score(
                warning_count=warning_count,
                unanswered_count=unanswered_count,
            )

        feedback_by_question_id = {
            item.get("question_id"): item
            for item in items
            if item.get("question_id")
        }
        competency_buckets: dict[str, dict[str, Any]] = {}

        for question in question_set:
            competency_key = question.get("competency_key")
            if not competency_key:
                continue

            bucket = competency_buckets.setdefault(
                competency_key,
                {
                    "competency_key": competency_key,
                    "competency_name": question.get("competency_name")
                    or question.get("requirement_text")
                    or competency_key,
                    "question_count": 0,
                    "answered_count": 0,
                    "warning_count": 0,
                },
            )
            bucket["question_count"] += 1

            feedback_item = feedback_by_question_id.get(question.get("question_id"))
            if feedback_item and feedback_item.get("answer_length", 0) > 0:
                bucket["answered_count"] += 1
            if feedback_item:
                bucket["warning_count"] += len(feedback_item.get("warnings", []))

        competency_readiness: list[dict[str, Any]] = []
        for bucket in competency_buckets.values():
            competency_unanswered_count = max(
                0,
                bucket["question_count"] - bucket["answered_count"],
            )
            competency_readiness.append(
                {
                    **bucket,
                    "readiness_score": self._calculate_readiness_score(
                        warning_count=bucket["warning_count"],
                        unanswered_count=competency_unanswered_count,
                    ),
                }
            )

        score_draft = InterviewScoreDraft(
            overall=None,
            by_category={},
            readiness_score=readiness_score,
        )

        serialized = serialize_score(score_draft)

        validated = InterviewSessionSchema(
            score={
                "score_version": "deterministic_v3",
                "question_count": question_count,
                "answered_count": answered_count,
                "unanswered_count": unanswered_count,
                "warning_count": warning_count,
                "competency_readiness": competency_readiness,
                **serialized,
            }
        )
        return validated.score.model_dump()

    @staticmethod
    def _calculate_readiness_score(
        *,
        warning_count: int,
        unanswered_count: int,
    ) -> int:
        raw_score = 100
        raw_score -= warning_count * 15
        raw_score -= unanswered_count * 8
        return max(0, min(100, raw_score))

    def _count_star_markers(self, answer_lower: str) -> int:
        markers = [
            "situation",
            "task",
            "action",
            "result",
            "ситуация",
            "задача",
            "действие",
            "действия",
            "результат",
        ]
        return sum(1 for marker in markers if marker in answer_lower)

    def _find_overclaim_phrases(self, answer_lower: str) -> list[str]:
        risky_phrases = [
            "expert",
            "senior",
            "production experience",
            "commercial experience",
            "эксперт",
            "сеньор",
            "senior-разработчик",
            "уверенный опыт",
            "коммерческий опыт",
            "глубокий опыт",
        ]
        return [phrase for phrase in risky_phrases if phrase in answer_lower]

    def _contains_unverified_metric(self, answer_text: str) -> bool:
        return "%" in answer_text

    def _word_count(self, text: str) -> int:
        return len(text.split())

    def _is_safe_enhancement(self, original: str, enhanced: str) -> bool:
        orig_words = self._word_count(original)
        enh_words = self._word_count(enhanced)

        if enh_words > orig_words * 5:
            return False

        return True

    @staticmethod
    def build_competency_key(text: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", text.strip().lower())
        normalized = normalized.strip("_")
        return normalized or "general_competency"

    def compute_progress(self, attempts: list) -> dict:
        if not attempts:
            return {
                "first_score": None,
                "last_score": None,
                "improvement": None,
            }

        scores = [a.score for a in attempts if a.score is not None]

        if not scores:
            return {
                "first_score": None,
                "last_score": None,
                "improvement": None,
            }

        return {
            "first_score": scores[0],
            "last_score": scores[-1],
            "improvement": scores[-1] - scores[0],
        }

    @staticmethod
    def build_attempt_diff(prev: str, current: str) -> dict:
        prev_words = set(prev.lower().split())
        curr_words = set(current.lower().split())

        added = list(curr_words - prev_words)
        removed = list(prev_words - curr_words)

        return {
            "added_keywords": added[:10],
            "removed_keywords": removed[:10],
        }

    @staticmethod
    def build_attempt_insight(prev_attempt, current_attempt) -> dict:
        diff = InterviewPreparationService.build_attempt_diff(
            prev_attempt.answer_text or "",
            current_attempt.answer_text or "",
        )

        improved = (current_attempt.score or 0) > (prev_attempt.score or 0)
        score_delta = (current_attempt.score or 0) - (prev_attempt.score or 0)

        return {
            "improved": improved,
            "score_delta": score_delta,
            "diff": diff,
        }

    def evaluate_answer(
        self,
        *,
        question: str,
        answer: str,
    ) -> dict:
        engine = AnswerEvaluationEngine(
            answer=answer,
            expected_competency=question,
        )
        checks = engine.evaluate()
        feedback = [check.message for check in checks if not check.passed]

        return {
            "score": engine.overall_score,
            "feedback": feedback,
            "checks": [asdict(check) for check in checks],
        }

    async def coach_answer(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        question: str,
        answer: str,
        evaluation: dict,
        language: str = "ru",
    ) -> dict:
        if not self.ai_orchestrator:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI orchestrator not configured",
            )

        from app.ai.use_cases.interview_coach import coach_answer

        result = await coach_answer(
            self.ai_orchestrator,
            session,
            user_id=user_id,
            question=question,
            answer=answer,
            evaluation=evaluation,
            language=language,
        )

        improved = result["result"]["improved_answer"]

        if not self._is_safe_enhancement(answer, improved):
            return {
                "improved_answer": answer,
                "explanation": "AI suggestion rejected (safety guard)",
            }

        return result["result"]

    async def improve_answer_with_ai(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        question: str,
        answer: str,
        evaluation: dict,
        language: str = "ru",
    ) -> dict:
        if not self.ai_orchestrator:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI orchestrator not configured",
            )

        from app.ai.use_cases.interview_coach import coach_answer

        result = await coach_answer(
            self.ai_orchestrator,
            session,
            user_id=user_id,
            question=question,
            answer=answer,
            evaluation=evaluation,
            language=language,
        )

        return result["result"]

    async def generate_coaching_hint(
        self,
        *,
        prev_attempt,
        current_attempt,
        diff: dict,
        orchestrator: Any,
        session: AsyncSession,
        user_id: UUID,
    ):
        from app.ai.use_cases.interview_coach import coach_attempts

        result = await coach_attempts(
            orchestrator,
            session,
            user_id=user_id,
            prev_attempt=prev_attempt,
            current_attempt=current_attempt,
            diff=diff,
        )

        return result["result"]

    def _build_question_set(
        self,
        *,
        vacancy_title: str,
        company: str | None,
        must_have: list[dict],
        nice_to_have: list[dict],
        strengths: list[dict],
        gaps: list[dict],
        achievements: list[dict],
    ) -> list[dict]:
        company_part = company or "компании"
        questions: list[InterviewQuestionDraft] = []

        questions.append(
            InterviewQuestionDraft(
                type="role_overview",
                source="vacancy",
                prompt=(
                    f"Кратко объясните, почему вам интересна позиция {vacancy_title} "
                    f"в {company_part} и чем ваш опыт может быть релевантен этой роли."
                ),
                answer_format="short_structured",
                rubric=[
                    "Показывает понимание роли",
                    "Связывает мотивацию с релевантным опытом",
                    "Не содержит неподтверждённых утверждений",
                ],
            )
        )

        for item in must_have[:6]:
            requirement_text = item.get("text")
            if not requirement_text:
                continue

            competency_key = self.build_competency_key(requirement_text)

            questions.append(
                InterviewQuestionDraft(
                    type="must_have_requirement",
                    source="vacancy_analysis.must_have",
                    competency_key=competency_key,
                    competency_name=requirement_text,
                    requirement_text=requirement_text,
                    prompt=(
                        f"Опишите ваш практический опыт по этому требованию: "
                        f"{requirement_text}."
                    ),
                    answer_format="STAR_or_example",
                    rubric=[
                        "Есть конкретный пример",
                        "Личный вклад отделён от командного контекста",
                        "Инструменты, масштаб и результат указаны только там, где это фактологично",
                    ],
                )
            )

        for item in gaps[:5]:
            keyword = item.get("keyword")
            requirement_text = item.get("requirement_text") or keyword
            if not keyword:
                continue

            competency_name = requirement_text or keyword
            competency_key = self.build_competency_key(competency_name)

            questions.append(
                InterviewQuestionDraft(
                    type="gap_preparation",
                    source="vacancy_analysis.gaps",
                    competency_key=competency_key,
                    competency_name=competency_name,
                    keyword=keyword,
                    requirement_text=requirement_text,
                    prompt=(
                        f"В вакансии ожидается {requirement_text}, но текущий профиль пока "
                        f"не даёт сильного подтверждения. Как честно ответить на вопрос "
                        f"о вашем уровне в {keyword}?"
                    ),
                    answer_format="honest_gap_response",
                    rubric=[
                        "Не выдумывает опыт",
                        "Чётко называет реальный уровень знакомства с темой",
                        "Показывает реалистичный план дообучения или переноса смежного опыта",
                    ],
                )
            )

        for item in strengths[:5]:
            keyword = item.get("keyword")
            requirement_text = item.get("requirement_text") or keyword
            if not keyword:
                continue

            competency_name = requirement_text or keyword
            competency_key = self.build_competency_key(competency_name)

            questions.append(
                InterviewQuestionDraft(
                    type="strength_deep_dive",
                    source="vacancy_analysis.strengths",
                    competency_key=competency_key,
                    competency_name=competency_name,
                    keyword=keyword,
                    requirement_text=requirement_text,
                    prompt=(
                        f"Подготовьте более глубокий пример, который подтверждает ваш опыт "
                        f"с {keyword} в контексте требования: {requirement_text}."
                    ),
                    answer_format="STAR",
                    rubric=[
                        "Ситуация и задача понятны",
                        "Действия описаны конкретно",
                        "Результат фактологичен и не завышен",
                    ],
                )
            )

        for item in achievements[:3]:
            title = item.get("title")
            fact_status = item.get("fact_status")
            if not title:
                continue

            questions.append(
                InterviewQuestionDraft(
                    type="achievement_star_story",
                    source="candidate_achievements",
                    achievement_title=title,
                    fact_status=fact_status,
                    prompt=(
                        f"Превратите это достижение в STAR-историю для собеседования: {title}."
                    ),
                    answer_format="STAR",
                    rubric=[
                        "Факт достижения подтверждён перед сильным использованием",
                        "Личный вклад кандидата понятен",
                        "Не добавлены неподтверждённые метрики",
                    ],
                )
            )

        serialized = [
            serialize_question(q, index=index)
            for index, q in enumerate(questions[:15])
        ]
        validated = InterviewSessionSchema(question_set=serialized)
        return [q.model_dump() for q in validated.question_set]
