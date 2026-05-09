# app\services\document_validation_service.py

from __future__ import annotations

from app.schemas.json_contracts import (
    CoverLetterContent,
    ResumeContent,
)


DOCUMENT_SCHEMA_MAP = {
    "resume": ResumeContent,
    "cover_letter": CoverLetterContent,
}


def validate_document_content(
    *,
    document_kind: str,
    payload: dict,
) -> ResumeContent | CoverLetterContent:
    schema = DOCUMENT_SCHEMA_MAP.get(document_kind)

    if schema is None:
        raise ValueError(
            f"unsupported document_kind: {document_kind}"
        )

    return schema.model_validate(payload)
