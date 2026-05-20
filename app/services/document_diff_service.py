from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.document_diff import DocumentDiffResult, SectionDiff
from app.repositories.document_version_repository import DocumentVersionRepository


class DocumentDiffService:
    def __init__(
        self,
        document_version_repository: DocumentVersionRepository | None = None,
    ) -> None:
        self.document_version_repository = (
            document_version_repository or DocumentVersionRepository()
        )

    def compare_documents(self, base_document, target_document) -> DocumentDiffResult:
        if base_document.document_kind != target_document.document_kind:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="documents must have same document_kind",
            )

        base_sections = self._extract_sections(base_document)
        target_sections = self._extract_sections(target_document)

        diff_sections: list[SectionDiff] = []

        for section_name in ("skills", "matched_keywords", "summary_bullets"):
            section_diff = self._compare_string_list_section(
                section_name,
                base_sections.get(section_name, []),
                target_sections.get(section_name, []),
            )
            if self._has_changes(section_diff):
                diff_sections.append(section_diff)

        achievement_diff = self._compare_achievement_section(
            "selected_achievements",
            base_sections.get("selected_achievements", []),
            target_sections.get("selected_achievements", []),
        )
        if self._has_changes(achievement_diff):
            diff_sections.append(achievement_diff)

        claims_diff = self._compare_claim_section(
            "claims_needing_confirmation",
            base_sections.get("claims_needing_confirmation", []),
            target_sections.get("claims_needing_confirmation", []),
        )
        if self._has_changes(claims_diff):
            diff_sections.append(claims_diff)

        warnings_diff = self._compare_warning_section(
            "warnings",
            base_sections.get("warnings", []),
            target_sections.get("warnings", []),
        )
        if self._has_changes(warnings_diff):
            diff_sections.append(warnings_diff)

        return DocumentDiffResult(
            base_document_id=base_document.id,
            target_document_id=target_document.id,
            sections=diff_sections,
        )

    async def build_diff(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        document_id: UUID,
        other_document_id: UUID,
    ) -> dict[str, Any]:
        base_document = await self.document_version_repository.get_by_id(
            session,
            document_id,
            user_id=user_id,
        )
        if base_document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="document not found",
            )

        target_document = await self.document_version_repository.get_by_id(
            session,
            other_document_id,
            user_id=user_id,
        )
        if target_document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="other document not found",
            )

        result = self.compare_documents(base_document, target_document)

        return {
            "base_document_id": result.base_document_id,
            "target_document_id": result.target_document_id,
            "document_kind": base_document.document_kind,
            "sections": [asdict(section) for section in result.sections],
            "summary": self.render_summary(result),
        }

    def render_summary(self, diff_result: DocumentDiffResult) -> str:
        lines: list[str] = []

        for section in diff_result.sections:
            label = self._humanize_section_name(section.section)

            for item in section.added:
                lines.append(f"+ {label}: {item}")

            for item in section.removed:
                lines.append(f"- {label}: {item}")

            for item in section.changed:
                lines.append(f"~ {label}: {item}")

        return "\n".join(lines)

    def _extract_sections(self, document) -> dict[str, Any]:
        content = document.content_json or {}
        sections = content.get("sections") or {}
        if not isinstance(sections, dict):
            return {}
        return sections

    def _compare_string_list_section(
        self,
        section_name: str,
        base_items: list[Any],
        target_items: list[Any],
    ) -> SectionDiff:
        base_values = self._normalized_string_list(base_items)
        target_values = self._normalized_string_list(target_items)

        base_lookup = {self._normalize_text(value): value for value in base_values}
        target_lookup = {self._normalize_text(value): value for value in target_values}

        added = [
            target_lookup[self._normalize_text(key)]
            for key in target_values
            if self._normalize_text(key) not in base_lookup
        ]
        removed = [
            base_lookup[self._normalize_text(key)]
            for key in base_values
            if self._normalize_text(key) not in target_lookup
        ]

        return SectionDiff(
            section=section_name,
            added=added,
            removed=removed,
            changed=[],
        )

    def _compare_achievement_section(
        self,
        section_name: str,
        base_items: list[Any],
        target_items: list[Any],
    ) -> SectionDiff:
        base_map = self._index_items_by_title(base_items)
        target_map = self._index_items_by_title(target_items)

        added = [
            self._achievement_title(item)
            for item in target_items
            if self._achievement_title(item)
            not in base_map
        ]

        removed = [
            self._achievement_title(item)
            for item in base_items
            if self._achievement_title(item)
            not in target_map
        ]

        changed: list[str] = []
        for title in self._ordered_titles(base_items, target_items):
            base_item = base_map.get(title)
            target_item = target_map.get(title)
            if base_item is None or target_item is None:
                continue
            if self._normalize_achievement_payload(base_item) != self._normalize_achievement_payload(target_item):
                changed.append(title)

        return SectionDiff(
            section=section_name,
            added=added,
            removed=removed,
            changed=changed,
        )

    def _compare_claim_section(
        self,
        section_name: str,
        base_items: list[Any],
        target_items: list[Any],
    ) -> SectionDiff:
        base_values = self._claim_texts(base_items)
        target_values = self._claim_texts(target_items)

        base_lookup = {self._normalize_text(value): value for value in base_values}
        target_lookup = {self._normalize_text(value): value for value in target_values}

        added = [
            target_lookup[self._normalize_text(key)]
            for key in target_values
            if self._normalize_text(key) not in base_lookup
        ]

        return SectionDiff(
            section=section_name,
            added=added,
            removed=[],
            changed=[],
        )

    def _compare_warning_section(
        self,
        section_name: str,
        base_items: list[Any],
        target_items: list[Any],
    ) -> SectionDiff:
        base_values = self._warning_texts(base_items)
        target_values = self._warning_texts(target_items)

        base_lookup = {self._normalize_text(value): value for value in base_values}
        target_lookup = {self._normalize_text(value): value for value in target_values}

        added = [
            target_lookup[self._normalize_text(key)]
            for key in target_values
            if self._normalize_text(key) not in base_lookup
        ]

        return SectionDiff(
            section=section_name,
            added=added,
            removed=[],
            changed=[],
        )

    def _has_changes(self, section_diff: SectionDiff) -> bool:
        return bool(section_diff.added or section_diff.removed or section_diff.changed)

    def _normalized_string_list(self, values: list[Any]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for value in values or []:
            if value is None:
                continue
            text = str(value).strip()
            key = self._normalize_text(text)
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append(text)

        return normalized

    def _claim_texts(self, values: list[Any]) -> list[str]:
        return self._normalized_string_list(
            [self._claim_text(item) for item in values]
        )

    def _warning_texts(self, values: list[Any]) -> list[str]:
        return self._normalized_string_list(
            [self._warning_text(item) for item in values]
        )

    def _index_items_by_title(self, items: list[Any]) -> dict[str, Any]:
        indexed: dict[str, Any] = {}

        for item in items or []:
            title = self._achievement_title(item)
            if not title:
                continue
            indexed.setdefault(title, item)

        return indexed

    def _ordered_titles(self, base_items: list[Any], target_items: list[Any]) -> list[str]:
        titles: list[str] = []
        seen: set[str] = set()

        for item in list(base_items or []) + list(target_items or []):
            title = self._achievement_title(item)
            if not title or title in seen:
                continue
            seen.add(title)
            titles.append(title)

        return titles

    def _achievement_title(self, item: Any) -> str:
        if isinstance(item, dict):
            return str(item.get("title") or "").strip()
        return str(item or "").strip()

    def _normalize_achievement_payload(self, item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {"value": str(item).strip()}

        normalized: dict[str, Any] = {}
        for key, value in item.items():
            if key == "title":
                continue
            normalized[key] = value
        return normalized

    def _claim_text(self, item: Any) -> str:
        if isinstance(item, dict):
            return str(item.get("text") or item.get("claim_text") or "").strip()
        return str(item or "").strip()

    def _warning_text(self, item: Any) -> str:
        if isinstance(item, dict):
            code = str(item.get("code") or "").strip()
            message = str(item.get("message") or item.get("text") or "").strip()
            if code and message:
                return f"{code}: {message}"
            return message or code
        return str(item or "").strip()

    def _humanize_section_name(self, section_name: str) -> str:
        return {
            "skills": "skill",
            "matched_keywords": "keyword",
            "summary_bullets": "summary bullet",
            "selected_achievements": "achievement",
            "claims_needing_confirmation": "claim requiring confirmation",
            "warnings": "warning",
        }.get(section_name, section_name.replace("_", " "))

    def _normalize_text(self, value: str) -> str:
        return " ".join(str(value).split()).casefold()
