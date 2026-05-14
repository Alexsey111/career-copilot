"""DocumentMutationService — безопасное изменение документов через создание версий."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentVersion
from app.repositories.document_version_repository import DocumentVersionRepository


class DocumentMutationError(Exception):
    """Ошибка при мутации документа."""
    pass


class DocumentMutationService:
    """
    Сервис для безопасного изменения документов.

    Ответственность ТОЛЬКО:
    - create new document version
    - apply structured patch
    - maintain lineage

    ВАЖНО: НЕ UPDATE EXISTING DOCUMENT.
    Только: old version → new version
    """

    def __init__(
        self,
        document_repository: DocumentVersionRepository,
    ) -> None:
        self._doc_repository = document_repository

    async def apply_changes(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        changes: dict[str, Any],
        user_id: UUID,
        version_label: str | None = None,
        change_reason: str | None = None,
    ) -> DocumentVersion:
        """
        Применяет изменения к документу, создавая новую версию.

        Args:
            session: Database session
            document_id: ID исходного документа
            changes: Структурированные изменения для применения
            user_id: ID пользователя (для валидации доступа)
            version_label: Опциональная метка версии
            change_reason: Причина изменений (для аудита)

        Returns:
            Новая версия документа

        Raises:
            DocumentMutationError: Если документ не найден или доступ запрещён
        """
        # 1. Получаем исходный документ
        source_document = await self._doc_repository.get_by_id(
            session, document_id, user_id=user_id
        )
        if not source_document:
            raise DocumentMutationError(f"Document {document_id} not found")

        # 2. Деактивируем все активные версии в том же scope
        await self._doc_repository.deactivate_same_scope(
            session,
            user_id=user_id,
            vacancy_id=source_document.vacancy_id,
            document_kind=source_document.document_kind,
            exclude_document_id=document_id,
        )

        # 3. Создаём новую версию
        new_content = self._apply_patch(source_document.content_json, changes)

        new_document = await self._doc_repository.create(
            session,
            user_id=user_id,
            vacancy_id=source_document.vacancy_id,
            derived_from_id=source_document.id,
            analysis_id=source_document.analysis_id,
            document_kind=source_document.document_kind,
            version_label=version_label or self._generate_version_label(source_document),
            review_status="draft",
            is_active=True,
            content_json=new_content,
            rendered_text=source_document.rendered_text,
        )

        # 4. Добавляем metadata об изменениях
        await self._add_mutation_metadata(new_document, changes, change_reason)

        return new_document

    async def apply_recommendation(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        recommendation_id: str,
        changes: dict[str, Any],
        user_id: UUID,
    ) -> DocumentVersion:
        """
        Применяет рекомендацию к документу.

        Convenience method для использования в ReviewActionLoop.

        Args:
            session: Database session
            document_id: ID документа для изменения
            recommendation_id: ID рекомендации
            changes: Изменения для применения
            user_id: ID пользователя

        Returns:
            Новая версия документа
        """
        version_label = f"rec-{recommendation_id[:8]}"
        change_reason = f"Applied recommendation: {recommendation_id}"

        return await self.apply_changes(
            session=session,
            document_id=document_id,
            changes=changes,
            user_id=user_id,
            version_label=version_label,
            change_reason=change_reason,
        )

    def _apply_patch(
        self,
        base_content: dict[str, Any],
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Применяет структурированный patch к контенту.

        Поддерживаемые операции в changes:
        - {"section": "experience", "index": 0, "field": "company", "value": "New Co"}
        - {"section": "summary", "operation": "append", "value": "New text"}
        - {"section": "achievements", "operation": "add", "item": {...}}

        Args:
            base_content: Базовый контент
            changes: Структурированные изменения

        Returns:
            Обновлённый контент
        """
        import copy
        result = copy.deepcopy(base_content)

        for change in changes.get("operations", [changes]):
            section = change.get("section")
            operation = change.get("operation", "set")

            if section and section in result:
                section_data = result[section]

                match operation:
                    case "set":
                        field = change.get("field")
                        value = change.get("value")
                        if field:
                            if isinstance(section_data, dict):
                                section_data[field] = value
                            elif isinstance(section_data, list):
                                index = change.get("index", 0)
                                if 0 <= index < len(section_data):
                                    section_data[index] = value
                    case "append":
                        value = change.get("value")
                        if isinstance(section_data, str):
                            result[section] = section_data + " " + value
                        elif isinstance(section_data, list):
                            section_data.append(value)
                    case "add":
                        item = change.get("item")
                        if isinstance(section_data, list) and item:
                            section_data.append(item)
                    case "remove":
                        index = change.get("index")
                        if isinstance(section_data, list) and index is not None:
                            if 0 <= index < len(section_data):
                                section_data.pop(index)
                    case "merge":
                        extra = change.get("extra", {})
                        if isinstance(section_data, dict):
                            section_data.update(extra)

        return result

    def _generate_version_label(self, source_document: DocumentVersion) -> str:
        """Генерирует метку версии на основе текущей."""
        current_label = source_document.version_label or "v1"

        # Пробуем инкрементировать число
        if current_label.startswith("v"):
            try:
                version_num = int(current_label[1:])
                return f"v{version_num + 1}"
            except ValueError:
                pass

        return f"{current_label}-modified"

    async def _add_mutation_metadata(
        self,
        document: DocumentVersion,
        changes: dict[str, Any],
        change_reason: str | None,
    ) -> None:
        """Добавляет metadata об изменениях в контент документа."""
        if "mutation_history" not in document.content_json:
            document.content_json["mutation_history"] = []

        mutation_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "changes": changes,
            "reason": change_reason,
        }

        document.content_json["mutation_history"].append(mutation_record)
        document.rendered_text = None  # Сброс рендеринга
