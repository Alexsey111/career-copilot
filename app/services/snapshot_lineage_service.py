"""Snapshot lineage traversal service for branchable evaluation DAGs."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation_snapshot import EvaluationSnapshot
from app.repositories.evaluation_snapshot_repository import EvaluationSnapshotRepository


@dataclass(slots=True)
class SnapshotBranch:
    """Linearized branch view for a snapshot lineage path."""

    root_to_snapshot: list[EvaluationSnapshot]

    @property
    def head(self) -> EvaluationSnapshot | None:
        return self.root_to_snapshot[-1] if self.root_to_snapshot else None


class SnapshotLineageService:
    """
    Traversal tooling for evaluation snapshot DAGs.

    Keeps the traversal logic separate from analytics so the repository and
    metrics code stay simple.
    """

    def __init__(self, repository: EvaluationSnapshotRepository) -> None:
        self._repository = repository

    async def get_ancestors(
        self,
        session: AsyncSession,
        snapshot_id: UUID,
        *,
        include_self: bool = False,
    ) -> list[EvaluationSnapshot]:
        """Return ancestors from root to the immediate parent."""
        branch = await self.get_branch(session, snapshot_id, include_self=True)
        if include_self:
            return branch.root_to_snapshot
        return branch.root_to_snapshot[:-1]

    async def get_branch(
        self,
        session: AsyncSession,
        snapshot_id: UUID,
        *,
        include_self: bool = True,
    ) -> SnapshotBranch:
        """Return the linear branch from root to the given snapshot."""
        snapshots, _ = await self._load_document_graph(session, snapshot_id=snapshot_id)
        by_id = {snapshot.id: snapshot for snapshot in snapshots}

        current = by_id.get(snapshot_id)
        if current is None:
            return SnapshotBranch(root_to_snapshot=[])

        path: list[EvaluationSnapshot] = []
        visited: set[UUID] = set()
        while current and current.id not in visited:
            visited.add(current.id)
            path.append(current)
            if current.previous_snapshot_id is None:
                break
            current = by_id.get(current.previous_snapshot_id)

        path.reverse()
        if not include_self and path:
            path = path[:-1]
        return SnapshotBranch(root_to_snapshot=path)

    async def get_descendants(
        self,
        session: AsyncSession,
        snapshot_id: UUID,
        *,
        include_self: bool = False,
    ) -> list[EvaluationSnapshot]:
        """Return all descendants reachable from the snapshot."""
        snapshots, children_map = await self._load_document_graph(session, snapshot_id=snapshot_id)
        by_id = {snapshot.id: snapshot for snapshot in snapshots}

        root = by_id.get(snapshot_id)
        if root is None:
            return []

        result: list[EvaluationSnapshot] = [root] if include_self else []
        queue: deque[EvaluationSnapshot] = deque(children_map.get(root.id, []))
        visited: set[UUID] = {root.id}

        while queue:
            current = queue.popleft()
            if current.id in visited:
                continue
            visited.add(current.id)
            result.append(current)
            for child in children_map.get(current.id, []):
                if child.id not in visited:
                    queue.append(child)

        return result

    async def get_branch_heads(
        self,
        session: AsyncSession,
        document_id: UUID,
    ) -> list[EvaluationSnapshot]:
        """Return all leaf snapshots for a document."""
        snapshots = await self._repository.get_by_document_id(session, document_id)
        by_parent: dict[UUID | None, list[EvaluationSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            by_parent[snapshot.previous_snapshot_id].append(snapshot)

        heads = [snapshot for snapshot in snapshots if snapshot.id not in by_parent]
        return sorted(heads, key=lambda snapshot: snapshot.created_at)

    async def find_common_ancestor(
        self,
        session: AsyncSession,
        first_snapshot_id: UUID,
        second_snapshot_id: UUID,
    ) -> EvaluationSnapshot | None:
        """Return the deepest common ancestor for two snapshots."""
        first_branch = await self.get_branch(session, first_snapshot_id)
        second_branch = await self.get_branch(session, second_snapshot_id)

        first_by_id = {snapshot.id: snapshot for snapshot in first_branch.root_to_snapshot}
        second_ids = {snapshot.id for snapshot in second_branch.root_to_snapshot}

        common: list[EvaluationSnapshot] = [
            snapshot
            for snapshot in first_branch.root_to_snapshot
            if snapshot.id in second_ids
        ]
        if not common:
            return None
        return common[-1]

    async def _load_document_graph(
        self,
        session: AsyncSession,
        *,
        snapshot_id: UUID,
    ) -> tuple[list[EvaluationSnapshot], dict[UUID, list[EvaluationSnapshot]]]:
        """Load all snapshots for the document containing the given snapshot."""
        current = await self._repository.get_by_id(session, snapshot_id)
        if current is None:
            return [], {}

        snapshots = await self._repository.get_by_document_id(session, current.document_id)
        children_map: dict[UUID, list[EvaluationSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            if snapshot.previous_snapshot_id is not None:
                children_map[snapshot.previous_snapshot_id].append(snapshot)

        for children in children_map.values():
            children.sort(key=lambda snapshot: snapshot.created_at)

        return snapshots, children_map
