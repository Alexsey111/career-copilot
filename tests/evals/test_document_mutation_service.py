"""Tests for DocumentMutationService."""

from uuid import uuid4

import pytest

from app.services.document_mutation_service import (
    DocumentMutationService,
    DocumentMutationError,
)


class TestDocumentMutationService:
    """Tests for document mutation operations."""

    def test_apply_patch_simple_set(self) -> None:
        """Test simple field update via patch."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        base = {"summary": {"text": "Hello world"}}
        changes = {"operations": [{"section": "summary", "operation": "set", "field": "text", "value": "New text"}]}

        result = service._apply_patch(base, changes)

        assert result["summary"]["text"] == "New text"

    def test_apply_patch_append_string(self) -> None:
        """Test appending to string field."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        base = {"summary": "Original text"}
        changes = {"operations": [{"section": "summary", "operation": "append", "value": "Added"}]}

        result = service._apply_patch(base, changes)

        assert result["summary"] == "Original text Added"

    def test_apply_patch_append_list(self) -> None:
        """Test appending to list field."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        base = {"skills": ["Python", "SQL"]}
        changes = {"operations": [{"section": "skills", "operation": "append", "value": "Docker"}]}

        result = service._apply_patch(base, changes)

        assert result["skills"] == ["Python", "SQL", "Docker"]

    def test_apply_patch_add_to_list(self) -> None:
        """Test adding item to list."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        base = {"experience": [{"company": "Old Co"}]}
        changes = {
            "operations": [
                {"section": "experience", "operation": "add", "item": {"company": "New Co"}}
            ]
        }

        result = service._apply_patch(base, changes)

        assert len(result["experience"]) == 2
        assert result["experience"][1]["company"] == "New Co"

    def test_apply_patch_merge_dict(self) -> None:
        """Test merging additional fields into dict."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        base = {"profile": {"name": "John"}}
        changes = {
            "operations": [
                {"section": "profile", "operation": "merge", "extra": {"email": "john@example.com"}}
            ]
        }

        result = service._apply_patch(base, changes)

        assert result["profile"]["name"] == "John"
        assert result["profile"]["email"] == "john@example.com"

    def test_apply_patch_remove_from_list(self) -> None:
        """Test removing item from list by index."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        base = {"achievements": ["First", "Second", "Third"]}
        changes = {"operations": [{"section": "achievements", "operation": "remove", "index": 1}]}

        result = service._apply_patch(base, changes)

        assert result["achievements"] == ["First", "Third"]

    def test_apply_patch_deep_copy(self) -> None:
        """Test that patch doesn't modify original."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        base = {"data": {"nested": "value"}}
        base_copy = {"data": {"nested": "value"}}  # Keep for comparison
        changes = {"operations": [{"section": "data", "operation": "merge", "extra": {"new": "field"}}]}

        result = service._apply_patch(base, changes)

        # Original should not be modified
        assert "new" not in base["data"]
        assert base == base_copy

        # Result should have new field
        assert result["data"]["new"] == "field"

    def test_generate_version_label_increment(self) -> None:
        """Test version label generation with numeric labels."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        from app.models import DocumentVersion

        doc = DocumentVersion(
            id=uuid4(),
            user_id=uuid4(),
            document_kind="resume",
            version_label="v3",
            review_status="draft",
            is_active=True,
            content_json={},
        )

        label = service._generate_version_label(doc)

        assert label == "v4"

    def test_generate_version_label_custom(self) -> None:
        """Test version label with non-numeric label."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        from app.models import DocumentVersion

        doc = DocumentVersion(
            id=uuid4(),
            user_id=uuid4(),
            document_kind="resume",
            version_label="initial",
            review_status="draft",
            is_active=True,
            content_json={},
        )

        label = service._generate_version_label(doc)

        assert label == "initial-modified"

    def test_apply_patch_no_section(self) -> None:
        """Test patch with non-existent section."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        base = {"existing": "data"}
        changes = {"operations": [{"section": "nonexistent", "operation": "set", "field": "value", "value": "test"}]}

        result = service._apply_patch(base, changes)

        # Should not modify anything
        assert result == base

    def test_apply_patch_empty_changes(self) -> None:
        """Test patch with empty changes."""
        service = DocumentMutationService(document_repository=None)  # type: ignore

        base = {"data": "value"}
        changes = {}

        result = service._apply_patch(base, changes)

        assert result == base
