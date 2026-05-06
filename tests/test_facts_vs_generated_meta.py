"""
Тесты для separation "facts vs generated" через content_json.meta
"""

from __future__ import annotations

import pytest

from app.schemas.json_contracts import ContentMeta, ResumeContent, CoverLetterContent


def test_content_meta_default_values():
    """Проверяем дефолтные значения ContentMeta."""
    meta = ContentMeta()
    assert meta.source == "ai_generated"
    assert meta.based_on_achievements == []
    assert meta.based_on_analysis_id is None
    assert meta.confidence == 0.8
    assert meta.generation_prompt_version is None


def test_content_meta_custom_values():
    """Проверяем кастомные значения ContentMeta."""
    meta = ContentMeta(
        source="hybrid",
        based_on_achievements=["ach-1", "ach-2"],
        based_on_analysis_id="analysis-123",
        confidence=0.95,
        generation_prompt_version="resume_tailor_v1",
    )
    assert meta.source == "hybrid"
    assert meta.based_on_achievements == ["ach-1", "ach-2"]
    assert meta.based_on_analysis_id == "analysis-123"
    assert meta.confidence == 0.95
    assert meta.generation_prompt_version == "resume_tailor_v1"


def test_content_meta_confidence_bounds():
    """Проверяем границы confidence (0.0 - 1.0)."""
    with pytest.raises(ValueError):
        ContentMeta(confidence=1.5)

    with pytest.raises(ValueError):
        ContentMeta(confidence=-0.1)

    meta = ContentMeta(confidence=0.0)
    assert meta.confidence == 0.0

    meta = ContentMeta(confidence=1.0)
    assert meta.confidence == 1.0


def test_resume_content_includes_meta():
    """Проверяем, что ResumeContent включает meta."""
    content = ResumeContent(
        meta=ContentMeta(
            source="hybrid",
            based_on_achievements=["ach-1"],
            based_on_analysis_id="analysis-123",
            confidence=0.85,
        )
    )
    assert content.meta.source == "hybrid"
    assert content.meta.based_on_achievements == ["ach-1"]
    assert content.meta.based_on_analysis_id == "analysis-123"
    assert content.meta.confidence == 0.85


def test_cover_letter_content_includes_meta():
    """Проверяем, что CoverLetterContent включает meta."""
    content = CoverLetterContent(
        meta=ContentMeta(
            source="extracted",
            confidence=0.7,
        )
    )
    assert content.meta.source == "extracted"
    assert content.meta.confidence == 0.7


def test_resume_content_serialization():
    """Проверяем сериализацию ResumeContent с meta."""
    content = ResumeContent(
        meta=ContentMeta(
            source="hybrid",
            based_on_achievements=["ach-1", "ach-2"],
            based_on_analysis_id="analysis-123",
            confidence=0.9,
            generation_prompt_version="resume_tailor_v1",
            generated_at="2024-01-01T00:00:00+00:00",
        )
    )
    data = content.model_dump()
    assert data["meta"]["source"] == "hybrid"
    assert data["meta"]["based_on_achievements"] == ["ach-1", "ach-2"]
    assert data["meta"]["based_on_analysis_id"] == "analysis-123"
    assert data["meta"]["confidence"] == 0.9
    assert data["meta"]["generation_prompt_version"] == "resume_tailor_v1"
    assert data["meta"]["generated_at"] == "2024-01-01T00:00:00+00:00"
