"""ReadinessEvaluationService — чистый сервис вычисления readiness оценок."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.readiness_evaluation import (
    ReadinessEvaluation,
    ReadinessLevel,
    ComponentScore,
)
from app.models import EvaluationSnapshot
from app.repositories.document_version_repository import DocumentVersionRepository
from app.services.deterministic_scoring_service import DeterministicScoringService, ExtractedReadinessFeatures
from app.services.readiness_feature_extraction_service import ReadinessFeatureExtractionService

from dataclasses import dataclass


@dataclass(slots=True)
class EvaluationProvenance:
    """Provenance information for evaluation."""
    prompt_version: str
    extractor_version: str
    scoring_version: str
    model_name: str

if TYPE_CHECKING:
    from app.domain.readiness_models import ReadinessScore


class ReadinessEvaluationService:
    """
    Сервис для вычисления и сохранения readiness оценок.

    Ответственность ТОЛЬКО:
    - calculate evaluation
    - return canonical ReadinessEvaluation object
    - persist snapshot to database

    Никаких:
    - recommendation execution
    - document mutation
    - review logic
    """

    def __init__(
        self,
        feature_extraction_service: ReadinessFeatureExtractionService,
        scoring_service: DeterministicScoringService,
        document_repository: DocumentVersionRepository,
    ) -> None:
        self._feature_extraction = feature_extraction_service
        self._scoring_service = scoring_service
        self._doc_repository = document_repository

    async def evaluate_document(
        self,
        session: AsyncSession,
        document_id: UUID,
        user_id: UUID,
    ) -> tuple[ReadinessEvaluation, UUID]:
        """
        Вычисляет readiness evaluation для документа и сохраняет snapshot.

        Args:
            session: Database session
            document_id: ID документа для оценки
            user_id: ID пользователя (для валидации доступа)

        Returns:
            Tuple of (ReadinessEvaluation, snapshot_id)
        """
        # 1. Получаем документ
        document = await self._doc_repository.get_by_id(
            session, document_id, user_id=user_id
        )
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # 2. Извлекаем features через extraction service
        features = await self._feature_extraction.extract_features(
            session=session,
            document_id=document_id,
            vacancy_id=None,  # TODO: get vacancy_id from document
            user_id=user_id,
        )

        # 3. Вычисляем оценку через deterministic scoring service
        readiness_score = self._scoring_service.calculate_readiness(features)

        # 4. Создаем provenance
        provenance = EvaluationProvenance(
            prompt_version="v1.0",  # TODO: get from config/feature flags
            extractor_version="v1.0",  # TODO: get from config/feature flags
            scoring_version="v1.0",  # TODO: get from config/feature flags
            model_name="gpt-4",  # TODO: get from AI service
        )

        # 5. Преобразуем в ReadinessEvaluation
        evaluation = self._to_evaluation(readiness_score, document_id, provenance)

        # 6. Сохраняем snapshot
        snapshot = await self._save_snapshot(session, evaluation, document_id, provenance)

        return evaluation, snapshot.id

    def _to_evaluation(
        self,
        score: "ReadinessScore",
        document_id: UUID,
        provenance: EvaluationProvenance,
    ) -> ReadinessEvaluation:
        """Преобразует ReadinessScore в ReadinessEvaluation."""
        components: list[ComponentScore] = [
            ComponentScore(
                name="ats",
                score=score.ats_score,
                weight=0.20,
                explanation=self._explain_ats_score(score),
            ),
            ComponentScore(
                name="evidence",
                score=score.evidence_score,
                weight=0.25,
                explanation=self._explain_evidence_score(score),
            ),
            ComponentScore(
                name="coverage",
                score=score.coverage_score,
                weight=0.30,
                explanation=self._explain_coverage_score(score),
            ),
            ComponentScore(
                name="quality",
                score=score.quality_score,
                weight=0.10,
                explanation=self._explain_quality_score(score),
            ),
        ]

        # Определяем readiness level
        readiness_level = self._determine_readiness_level(score)

        return ReadinessEvaluation(
            overall_score=score.overall_score,
            ats_score=score.ats_score,
            evidence_score=score.evidence_score,
            coverage_score=score.coverage_score,
            quality_score=score.quality_score,
            readiness_level=readiness_level,
            scoring_version=provenance.scoring_version,
            prompt_version=provenance.prompt_version,
            extractor_version=provenance.extractor_version,
            model_name=provenance.model_name,
            evaluated_at=datetime.now(timezone.utc),
            components=components,
            blockers=score.blocking_issues,
            warnings=score.warnings,
            metadata={
                "document_id": str(document_id),
                "blocking_count": len(score.blocking_issues),
                "warning_count": len(score.warnings),
            },
        )

    def _determine_readiness_level(self, score: "ReadinessScore") -> ReadinessLevel:
        """Определяет уровень готовности на основе scores."""
        if score.is_ready:
            return ReadinessLevel.READY
        if score.overall_score >= 0.5:
            return ReadinessLevel.NEEDS_WORK
        return ReadinessLevel.NOT_READY

    def _explain_ats_score(self, score: "ReadinessScore") -> str:
        """Генерирует объяснение для ATS score."""
        if score.ats_score >= 0.8:
            return "Excellent keyword preservation"
        if score.ats_score >= 0.6:
            return "Good keyword preservation with minor gaps"
        if score.ats_score >= 0.4:
            return "Moderate keyword preservation - review ATS mapping"
        return "Poor keyword preservation - critical skills may be lost"

    def _explain_evidence_score(self, score: "ReadinessScore") -> str:
        """Генерирует объяснение для evidence score."""
        if score.evidence_score >= 0.8:
            return "Strong quantifiable evidence throughout"
        if score.evidence_score >= 0.6:
            return "Good evidence with some areas for improvement"
        if score.evidence_score >= 0.4:
            return "Limited quantifiable proof - add metrics"
        return "Weak evidence - achievements lack measurable outcomes"

    def _explain_coverage_score(self, score: "ReadinessScore") -> str:
        """Генерирует объяснение для coverage score."""
        if score.coverage_score >= 0.8:
            return "Comprehensive coverage of requirements"
        if score.coverage_score >= 0.6:
            return "Good coverage with some gaps"
        if score.coverage_score >= 0.4:
            return "Partial coverage - review requirements mapping"
        return "Insufficient coverage - major gaps in requirements"

    def _explain_quality_score(self, score: "ReadinessScore") -> str:
        """Генерирует объяснение для quality score."""
        if score.quality_score >= 0.8:
            return "High overall document quality"
        if score.quality_score >= 0.6:
            return "Good quality with minor improvements needed"
        if score.quality_score >= 0.4:
            return "Moderate quality - review structure and clarity"
        return "Low quality - significant improvements required"

    async def _save_snapshot(
        self,
        session: AsyncSession,
        evaluation: ReadinessEvaluation,
        document_id: UUID,
        provenance: EvaluationProvenance,
    ) -> EvaluationSnapshot:
        """Сохраняет evaluation snapshot в БД."""
        snapshot = EvaluationSnapshot(
            document_id=document_id,
            overall_score=evaluation.overall_score,
            ats_score=evaluation.ats_score,
            evidence_score=evaluation.evidence_score,
            coverage_score=evaluation.coverage_score,
            quality_score=evaluation.quality_score,
            readiness_level=evaluation.readiness_level.value,
            scoring_version=provenance.scoring_version,
            prompt_version=provenance.prompt_version,
            extractor_version=provenance.extractor_version,
            model_name=provenance.model_name,
            blockers_json=evaluation.blockers,
            warnings_json=evaluation.warnings,
            metadata_json=evaluation.metadata,
            created_at=evaluation.evaluated_at,
        )

        session.add(snapshot)
        await session.flush()
        await session.refresh(snapshot)

        return snapshot

    async def get_latest_snapshot(
        self,
        session: AsyncSession,
        document_id: UUID,
    ) -> EvaluationSnapshot | None:
        """Получает последний snapshot для документа."""
        from sqlalchemy import select
        from app.models import EvaluationSnapshot as SnapshotModel

        stmt = (
            select(SnapshotModel)
            .where(SnapshotModel.document_id == document_id)
            .order_by(SnapshotModel.created_at.desc())
            .limit(1)
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()
