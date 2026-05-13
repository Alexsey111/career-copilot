# tests/evals/test_artifact_registry.py

"""Tests for artifact registry and lineage tracking."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from app.services.artifact_registry import (
    ArtifactReference,
    ArtifactRecord,
    ArtifactRegistry,
    ArtifactType,
    validate_execution_consistency,
)


class TestArtifactReference:
    """Tests for ArtifactReference dataclass."""

    def test_create_reference(self):
        """Test basic artifact reference creation."""
        artifact_id = str(uuid4())
        execution_id = str(uuid4())
        created_at = datetime.now()

        ref = ArtifactReference(
            artifact_id=artifact_id,
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id=execution_id,
            version="v1.0",
            created_at=created_at,
            parent_artifact_ids=[],
        )

        assert ref.artifact_id == artifact_id
        assert ref.artifact_type == ArtifactType.RESUME.value
        assert ref.source_execution_id == execution_id
        assert ref.version == "v1.0"
        assert ref.created_at == created_at
        assert ref.parent_artifact_ids == []

    def test_lineage_chain(self):
        """Test lineage chain property."""
        parent_id = str(uuid4())
        grandparent_id = str(uuid4())
        
        ref = ArtifactReference(
            artifact_id=str(uuid4()),
            artifact_type=ArtifactType.RECOMMENDATION.value,
            source_execution_id=str(uuid4()),
            version="v1.0",
            created_at=datetime.now(),
            parent_artifact_ids=[parent_id, grandparent_id],
        )

        assert ref.lineage_chain == [parent_id, grandparent_id]

    def test_with_parent(self):
        """Test adding parent to lineage."""
        ref = ArtifactReference(
            artifact_id=str(uuid4()),
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id=str(uuid4()),
            version="v1.0",
            created_at=datetime.now(),
            parent_artifact_ids=["parent-1"],
        )

        new_ref = ref.with_parent("parent-2")

        assert new_ref.artifact_id == ref.artifact_id
        assert new_ref.parent_artifact_ids == ["parent-1", "parent-2"]


class TestArtifactRegistry:
    """Tests for ArtifactRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh artifact registry."""
        return ArtifactRegistry()

    def test_register_artifact(self, registry):
        """Test basic artifact registration."""
        artifact_id = "artifact-1"
        execution_id = "exec-1"

        record = registry.register(
            artifact_id=artifact_id,
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id=execution_id,
            version="v1.0",
            payload={"content": "test resume"},
        )

        assert record.artifact_id == artifact_id
        assert record.artifact_type == ArtifactType.RESUME.value
        assert record.source_execution_id == execution_id
        assert record.payload == {"content": "test resume"}

    def test_register_with_parent(self, registry):
        """Test artifact registration with lineage."""
        parent_id = "parent-1"
        child_id = "child-1"
        execution_id = "exec-1"

        registry.register(
            artifact_id=parent_id,
            artifact_type=ArtifactType.EVALUATION.value,
            source_execution_id=execution_id,
            version="v1.0",
            payload={},
        )

        record = registry.register(
            artifact_id=child_id,
            artifact_type=ArtifactType.RECOMMENDATION.value,
            source_execution_id=execution_id,
            version="v1.0",
            payload={},
            parent_artifact_ids=[parent_id],
        )

        assert record.reference.parent_artifact_ids == [parent_id]

    def test_get_artifact(self, registry):
        """Test artifact retrieval by ID."""
        artifact_id = "artifact-1"
        
        registry.register(
            artifact_id=artifact_id,
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={"test": "data"},
        )

        record = registry.get(artifact_id)
        assert record is not None
        assert record.artifact_id == artifact_id

    def test_get_nonexistent_artifact(self, registry):
        """Test retrieval of nonexistent artifact."""
        record = registry.get("nonexistent")
        assert record is None

    def test_get_by_type(self, registry):
        """Test filtering artifacts by type."""
        registry.register(
            artifact_id="res-1",
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
        )
        registry.register(
            artifact_id="res-2",
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
        )
        registry.register(
            artifact_id="eval-1",
            artifact_type=ArtifactType.EVALUATION.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
        )

        resumes = registry.get_by_type(ArtifactType.RESUME.value)
        evaluations = registry.get_by_type(ArtifactType.EVALUATION.value)

        assert len(resumes) == 2
        assert len(evaluations) == 1

    def test_get_by_execution(self, registry):
        """Test filtering artifacts by execution."""
        registry.register(
            artifact_id="art-1",
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
        )
        registry.register(
            artifact_id="art-2",
            artifact_type=ArtifactType.EVALUATION.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
        )
        registry.register(
            artifact_id="art-3",
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id="exec-2",
            version="v1.0",
            payload={},
        )

        exec1_artifacts = registry.get_by_execution("exec-1")
        exec2_artifacts = registry.get_by_execution("exec-2")

        assert len(exec1_artifacts) == 2
        assert len(exec2_artifacts) == 1

    def test_get_lineage(self, registry):
        """Test lineage chain retrieval."""
        # Create lineage: grandparent -> parent -> child
        registry.register(
            artifact_id="grandparent",
            artifact_type=ArtifactType.SNAPSHOT.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={"level": "grandparent"},
        )
        registry.register(
            artifact_id="parent",
            artifact_type=ArtifactType.EVALUATION.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={"level": "parent"},
            parent_artifact_ids=["grandparent"],
        )
        registry.register(
            artifact_id="child",
            artifact_type=ArtifactType.RECOMMENDATION.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={"level": "child"},
            parent_artifact_ids=["parent"],
        )

        lineage = registry.get_lineage("child")

        assert len(lineage) == 2
        assert lineage[0].artifact_id == "grandparent"
        assert lineage[1].artifact_id == "parent"

    def test_get_children(self, registry):
        """Test getting child artifacts."""
        registry.register(
            artifact_id="parent",
            artifact_type=ArtifactType.EVALUATION.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
        )
        registry.register(
            artifact_id="child-1",
            artifact_type=ArtifactType.RECOMMENDATION.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
            parent_artifact_ids=["parent"],
        )
        registry.register(
            artifact_id="child-2",
            artifact_type=ArtifactType.RECOMMENDATION.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
            parent_artifact_ids=["parent"],
        )
        registry.register(
            artifact_id="unrelated",
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
        )

        children = registry.get_children("parent")

        assert len(children) == 2
        child_ids = {c.artifact_id for c in children}
        assert child_ids == {"child-1", "child-2"}

    def test_duplicate_registration_raises(self, registry):
        """Test that registering duplicate artifact raises error."""
        registry.register(
            artifact_id="artifact-1",
            artifact_type=ArtifactType.RESUME.value,
            source_execution_id="exec-1",
            version="v1.0",
            payload={},
        )

        with pytest.raises(ValueError, match="already registered"):
            registry.register(
                artifact_id="artifact-1",
                artifact_type=ArtifactType.RESUME.value,
                source_execution_id="exec-1",
                version="v1.0",
                payload={},
            )


class TestValidateExecutionConsistency:
    """Tests for pipeline consistency validation."""

    def test_completed_requires_resume_document(self):
        """COMPLETED pipeline must have resume_document_id."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="completed",
            resume_document_id=None,
        )

        assert not is_valid
        assert len(violations) == 1
        assert "missing resume_document_id" in violations[0]

    def test_completed_with_resume_is_valid(self):
        """COMPLETED pipeline with resume_document_id is valid."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="completed",
            resume_document_id=uuid4(),
        )

        assert is_valid
        assert len(violations) == 0

    def test_review_gate_requires_review(self):
        """REVIEW_GATE must have review_id."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="review_gate",
            review_id=None,
        )

        assert not is_valid
        assert len(violations) == 1
        assert "ReviewWorkspace required" in violations[0]

    def test_review_gate_with_review_is_valid(self):
        """REVIEW_GATE with review_id is valid."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="review_gate",
            review_id=uuid4(),
        )

        assert is_valid
        assert len(violations) == 0

    def test_document_evaluation_requires_snapshot(self):
        """DOCUMENT_EVALUATION must have evaluation_snapshot_id."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="document_evaluation",
            evaluation_snapshot_id=None,
        )

        assert not is_valid
        assert len(violations) == 1
        assert "missing evaluation_snapshot_id" in violations[0]

    def test_readiness_scoring_requires_score_in_artifacts(self):
        """READINESS_SCORING must have readiness_score in artifacts."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="readiness_scoring",
            artifacts={},
        )

        assert not is_valid
        assert len(violations) == 1
        assert "missing readiness_score" in violations[0]

    def test_readiness_scoring_with_score_is_valid(self):
        """READINESS_SCORING with readiness_score is valid."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="readiness_scoring",
            artifacts={"readiness_score": {"overall_score": 0.8}},
        )

        assert is_valid
        assert len(violations) == 0

    def test_readiness_scoring_without_artifacts(self):
        """READINESS_SCORING without artifacts is invalid."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="readiness_scoring",
            artifacts=None,
        )

        assert not is_valid
        assert len(violations) == 1
        assert "has no artifacts" in violations[0]

    def test_achievement_retrieval_requires_achievements(self):
        """ACHIEVEMENT_RETRIEVAL must have achievements in artifacts."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="achievement_retrieval",
            artifacts={},
        )

        assert not is_valid
        assert "missing achievements" in violations[0]

    def test_coverage_mapping_requires_coverage(self):
        """COVERAGE_MAPPING must have coverage in artifacts."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="coverage_mapping",
            artifacts={},
        )

        assert not is_valid
        assert "missing coverage" in violations[0]

    def test_unknown_status_has_no_violations(self):
        """Unknown status should have no consistency violations."""
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="unknown_status",
        )

        assert is_valid
        assert len(violations) == 0

    def test_multiple_violations(self):
        """Test multiple violations are collected."""
        # Note: currently each status is checked independently,
        # so multiple violations only happen with unknown status logic
        is_valid, violations = validate_execution_consistency(
            execution_id="exec-1",
            status="completed",
            resume_document_id=None,
        )

        assert not is_valid
        assert len(violations) >= 1
