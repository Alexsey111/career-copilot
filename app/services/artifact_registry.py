# app/services/artifact_registry.py

"""
Artifact Registry — explicit lineage tracking for AI pipeline artifacts.

Зачем:
- Сейчас много сущностей: resume, evaluation, review, readiness, recommendations, snapshots
- Но lineage был implicit
- Теперь explicit lineage для ответа на вопросы:
  - Из какого evaluation появился этот recommendation?
  - Какой resume использовался для readiness score?
- Критично для AI systems reproducibility и auditability
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


class ArtifactType(str, Enum):
    """Типы артефактов в pipeline."""
    RESUME = "resume"
    EVALUATION = "evaluation"
    REVIEW = "review"
    READINESS = "readiness"
    RECOMMENDATION = "recommendation"
    SNAPSHOT = "snapshot"
    COVERAGE = "coverage"
    EVIDENCE = "evidence"
    INTERVIEW_FEEDBACK = "interview_feedback"
    PACKAGE = "application_package"


@dataclass(slots=True)
class ArtifactReference:
    """
    Explicit reference to an artifact with full lineage tracking.

    Позволяет ответить:
    - Из какого evaluation появился этот recommendation?
    - Какой resume использовался для readiness score?
    """
    artifact_id: str
    artifact_type: str

    source_execution_id: str

    version: str
    created_at: datetime

    parent_artifact_ids: list[str] = field(default_factory=list)

    @property
    def lineage_chain(self) -> list[str]:
        """Полная цепочка предков от этого артефакта до корня."""
        return list(self.parent_artifact_ids)

    def with_parent(self, parent_id: str) -> ArtifactReference:
        """Добавляет родителя в цепочку lineage."""
        return ArtifactReference(
            artifact_id=self.artifact_id,
            artifact_type=self.artifact_type,
            source_execution_id=self.source_execution_id,
            version=self.version,
            created_at=self.created_at,
            parent_artifact_ids=[*self.parent_artifact_ids, parent_id],
        )


@dataclass(slots=True)
class ArtifactRecord:
    """Полная запись артефакта с метаданными."""
    reference: ArtifactReference
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def artifact_id(self) -> str:
        return self.reference.artifact_id

    @property
    def artifact_type(self) -> str:
        return self.reference.artifact_type

    @property
    def source_execution_id(self) -> str:
        return self.reference.source_execution_id


class ArtifactRegistry:
    """
    Registry для управления артефактами и их lineage.

    Обеспечивает:
    - Регистрация артефактов с explicit lineage
    - Отслеживание происхождения (откуда появился артефакт)
    - Поиск артефактов по типу и execution
    - Валидацию consistency pipeline
    """

    def __init__(self) -> None:
        self._artifacts: dict[str, ArtifactRecord] = {}
        self._artifacts_by_type: dict[str, list[str]] = {}
        self._artifacts_by_execution: dict[str, list[str]] = {}

    def register(
        self,
        artifact_id: str,
        artifact_type: str,
        source_execution_id: str,
        version: str,
        payload: dict[str, Any],
        parent_artifact_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> ArtifactRecord:
        """
        Регистрирует новый артефакт.

        Args:
            artifact_id: Уникальный ID артефакта
            artifact_type: Тип артефакта (см. ArtifactType)
            source_execution_id: ID pipeline execution, который создал артефакт
            version: Версия артефакта
            payload: Данные артефакта
            parent_artifact_ids: IDs родительских артефактов (lineage)
            metadata: Дополнительная метаданная
            created_at: Время создания

        Returns:
            ArtifactRecord с зарегистрированным артефактом
        """
        if artifact_id in self._artifacts:
            raise ValueError(f"Artifact {artifact_id} already registered")

        parent_ids = parent_artifact_ids or []
        created = created_at or datetime.now(timezone.utc)

        reference = ArtifactReference(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            source_execution_id=source_execution_id,
            version=version,
            created_at=created,
            parent_artifact_ids=parent_ids,
        )

        record = ArtifactRecord(
            reference=reference,
            payload=payload,
            metadata=metadata or {},
        )

        self._artifacts[artifact_id] = record

        # Индексация по типу
        if artifact_type not in self._artifacts_by_type:
            self._artifacts_by_type[artifact_type] = []
        self._artifacts_by_type[artifact_type].append(artifact_id)

        # Индексация по execution
        if source_execution_id not in self._artifacts_by_execution:
            self._artifacts_by_execution[source_execution_id] = []
        self._artifacts_by_execution[source_execution_id].append(artifact_id)

        return record

    def get(self, artifact_id: str) -> ArtifactRecord | None:
        """Получает артефакт по ID."""
        return self._artifacts.get(artifact_id)

    def get_by_type(self, artifact_type: str) -> list[ArtifactRecord]:
        """Получает все артефакты указанного типа."""
        artifact_ids = self._artifacts_by_type.get(artifact_type, [])
        return [self._artifacts[aid] for aid in artifact_ids if aid in self._artifacts]

    def get_by_execution(self, execution_id: str) -> list[ArtifactRecord]:
        """Получает все артефакты, созданные в рамках execution."""
        artifact_ids = self._artifacts_by_execution.get(execution_id, [])
        return [self._artifacts[aid] for aid in artifact_ids if aid in self._artifacts]

    def get_lineage(self, artifact_id: str) -> list[ArtifactRecord]:
        """
        Получает полную цепочку lineage артефакта (от корня до текущего).

        Returns:
            Список артефактов от самого старого родителя до текущего
        """
        record = self._artifacts.get(artifact_id)
        if not record:
            return []

        lineage = []
        current_ids = record.reference.parent_artifact_ids

        # Идем вверх по цепочке
        visited: set[str] = set()
        while current_ids:
            parent_id = current_ids[0]  # Берем первого родителя
            if parent_id in visited:
                break
            visited.add(parent_id)

            parent_record = self._artifacts.get(parent_id)
            if parent_record:
                lineage.insert(0, parent_record)
                current_ids = parent_record.reference.parent_artifact_ids
            else:
                break

        return lineage

    def get_children(self, artifact_id: str) -> list[ArtifactRecord]:
        """Получает все артефакты, которые произошли от указанного."""
        record = self._artifacts.get(artifact_id)
        if not record:
            return []

        children = []
        for other_record in self._artifacts.values():
            if artifact_id in other_record.reference.parent_artifact_ids:
                children.append(other_record)

        return children


def validate_execution_consistency(
    execution_id: str,
    status: str,
    artifacts: dict[str, Any] | None = None,
    resume_document_id: UUID | None = None,
    evaluation_snapshot_id: UUID | None = None,
    review_id: UUID | None = None,
) -> tuple[bool, list[str]]:
    """
    Проверяет consistency pipeline execution для данного статуса.

    Что проверяет:
    - COMPLETED pipeline → должен иметь resume_document_id
    - REVIEW_GATE → должен иметь ReviewWorkspace (review_id)
    - DOCUMENT_EVALUATION → должен иметь evaluation_snapshot_id
    - READINESS_SCORING → должен иметь readiness_score в artifacts

    Args:
        execution_id: ID pipeline execution
        status: Текущий статус PipelineStatus
        artifacts: JSON artifacts из execution
        resume_document_id: ID сгенерированного резюме
        evaluation_snapshot_id: ID vacancy analysis
        review_id: ID review workspace

    Returns:
        (is_valid, list_of_violations)
    """
    violations: list[str] = []

    # COMPLETED pipeline → должен иметь resume_document_id
    if status == "completed":
        if not resume_document_id:
            violations.append(
                f"COMPLETED execution {execution_id} missing resume_document_id"
            )

    # REVIEW_GATE → должен иметь ReviewWorkspace (review_id)
    if status == "review_gate":
        if not review_id:
            violations.append(
                f"REVIEW_GATE execution {execution_id} missing review_id (ReviewWorkspace required)"
            )

    # DOCUMENT_EVALUATION → должен иметь evaluation_snapshot_id
    if status == "document_evaluation":
        if not evaluation_snapshot_id:
            violations.append(
                f"DOCUMENT_EVALUATION execution {execution_id} missing evaluation_snapshot_id"
            )

    # READINESS_SCORING → должен иметь readiness_score в artifacts
    if status == "readiness_scoring":
        if artifacts is None:
            violations.append(
                f"READINESS_SCORING execution {execution_id} has no artifacts"
            )
        else:
            readiness_score = artifacts.get("readiness_score")
            if not readiness_score:
                violations.append(
                    f"READINESS_SCORING execution {execution_id} missing readiness_score in artifacts"
                )

    # ACHIEVEMENT_RETRIEVAL → должен иметь achievements в artifacts
    if status == "achievement_retrieval":
        if artifacts is None:
            violations.append(
                f"ACHIEVEMENT_RETRIEVAL execution {execution_id} has no artifacts"
            )
        else:
            achievements = artifacts.get("achievements")
            if not achievements:
                violations.append(
                    f"ACHIEVEMENT_RETRIEVAL execution {execution_id} missing achievements in artifacts"
                )

    # COVERAGE_MAPPING → должен иметь coverage data в artifacts
    if status == "coverage_mapping":
        if artifacts is None:
            violations.append(
                f"COVERAGE_MAPPING execution {execution_id} has no artifacts"
            )
        else:
            coverage = artifacts.get("coverage")
            if not coverage:
                violations.append(
                    f"COVERAGE_MAPPING execution {execution_id} missing coverage in artifacts"
                )

    is_valid = len(violations) == 0
    return is_valid, violations
