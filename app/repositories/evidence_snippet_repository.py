# D:\python projects\career-copilot\app\repositories\evidence_snippet_repository.py

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EvidenceSnippet, EvidenceUsage


class EvidenceSnippetRepository:
    async def upsert_many(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        snippets: Sequence[dict],
    ) -> list[EvidenceSnippet]:
        persisted: list[EvidenceSnippet] = []

        for item in snippets:
            fingerprint = str(item.get("fingerprint") or "").strip()
            if not fingerprint:
                continue

            existing = await self.get_by_fingerprint(
                session,
                user_id=user_id,
                fingerprint=fingerprint,
            )

            if existing is None:
                existing = EvidenceSnippet(
                    user_id=user_id,
                    fingerprint=fingerprint,
                    title=str(item.get("title") or "").strip() or "Evidence snippet",
                    snippet_text=str(item.get("snippet_text") or "").strip(),
                    source_type=str(item.get("source_type") or "achievement").strip().lower(),
                    skills_json=list(item.get("skills") or []),
                    evidence_strength=str(item.get("evidence_strength") or "weak").strip().lower(),
                    fact_status=str(item.get("fact_status") or "unverified").strip().lower(),
                    usage_count=int(item.get("usage_count") or 0),
                    used_in_documents_count=int(item.get("used_in_documents_count") or 0),
                    used_in_interviews_count=int(item.get("used_in_interviews_count") or 0),
                    star_summary_json=dict(item.get("star_summary") or {}),
                )
                session.add(existing)
            else:
                existing.title = str(item.get("title") or existing.title).strip() or existing.title
                existing.snippet_text = str(item.get("snippet_text") or existing.snippet_text).strip()
                existing.source_type = str(item.get("source_type") or existing.source_type).strip().lower()
                existing.skills_json = list(item.get("skills") or existing.skills_json or [])
                existing.evidence_strength = str(
                    item.get("evidence_strength") or existing.evidence_strength
                ).strip().lower()
                existing.fact_status = str(item.get("fact_status") or existing.fact_status).strip().lower()
                existing.star_summary_json = dict(item.get("star_summary") or existing.star_summary_json or {})

            persisted.append(existing)

        await session.flush()
        for snippet in persisted:
            await session.refresh(snippet)
        return persisted

    async def get_by_fingerprint(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        fingerprint: str,
    ) -> EvidenceSnippet | None:
        stmt = select(EvidenceSnippet).where(
            EvidenceSnippet.user_id == user_id,
            EvidenceSnippet.fingerprint == fingerprint,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        snippet_id: UUID,
    ) -> EvidenceSnippet | None:
        stmt = select(EvidenceSnippet).where(
            EvidenceSnippet.user_id == user_id,
            EvidenceSnippet.id == snippet_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user_id(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        source_types: Sequence[str] | None = None,
    ) -> list[EvidenceSnippet]:
        stmt = select(EvidenceSnippet).where(EvidenceSnippet.user_id == user_id)
        if source_types:
            normalized = [str(item).strip().lower() for item in source_types if str(item).strip()]
            if normalized:
                stmt = stmt.where(EvidenceSnippet.source_type.in_(normalized))

        stmt = stmt.order_by(
            EvidenceSnippet.usage_count.desc(),
            EvidenceSnippet.updated_at.desc(),
            EvidenceSnippet.created_at.desc(),
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def record_usage(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        evidence_snippet_id: UUID,
        usage_type: str,
        target_type: str | None = None,
        target_id: str | None = None,
        note: str | None = None,
    ) -> EvidenceUsage | None:
        snippet = await self.get_by_id_for_user(
            session,
            user_id=user_id,
            snippet_id=evidence_snippet_id,
        )
        if snippet is None:
            return None

        usage = EvidenceUsage(
            user_id=user_id,
            evidence_snippet_id=evidence_snippet_id,
            usage_type=str(usage_type).strip().lower(),
            target_type=str(target_type).strip().lower() if target_type else None,
            target_id=str(target_id).strip() if target_id else None,
            note=str(note).strip() if note else None,
        )
        snippet.usage_count += 1

        if usage.usage_type in {"document", "resume", "cover_letter"}:
            snippet.used_in_documents_count += 1
        elif usage.usage_type in {"interview", "interview_prep", "question"}:
            snippet.used_in_interviews_count += 1

        session.add(usage)
        await session.flush()
        await session.refresh(usage)
        await session.refresh(snippet)
        return usage

    async def list_usages_by_user_id(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
    ) -> list[EvidenceUsage]:
        stmt = select(EvidenceUsage).where(EvidenceUsage.user_id == user_id)
        stmt = stmt.order_by(
            EvidenceUsage.created_at.desc(),
            EvidenceUsage.updated_at.desc(),
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
