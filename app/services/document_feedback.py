# app\services\document_feedback.py

from __future__ import annotations

from app.schemas.json_contracts import ClaimItem, WarningItem


def build_warning(
    *,
    code: str,
    message: str,
    severity: str = "warning",
) -> WarningItem:
    return WarningItem(
        code=code,
        message=message,
        severity=severity,
    )


def build_claim(
    *,
    claim_type: str,
    text: str,
    fact_status: str,
    source: str | None = None,
) -> ClaimItem:
    return ClaimItem(
        type=claim_type,
        text=text,
        fact_status=fact_status,
        source=source,
    )
