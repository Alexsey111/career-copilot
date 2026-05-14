from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from app.repositories.evaluation_snapshot_repository import EvaluationSnapshotRepository
from app.services.snapshot_lineage_service import SnapshotLineageService


@dataclass(slots=True)
class FakeSnapshot:
    id: object
    document_id: object
    previous_snapshot_id: object | None
    created_at: datetime


class FakeSnapshotRepository(EvaluationSnapshotRepository):
    def __init__(self, snapshots: list[FakeSnapshot]) -> None:
        self._snapshots = snapshots

    async def get_by_id(self, session, snapshot_id):  # type: ignore[override]
        return next((snapshot for snapshot in self._snapshots if snapshot.id == snapshot_id), None)

    async def get_by_document_id(self, session, document_id, limit: int = 50):  # type: ignore[override]
        snapshots = [snapshot for snapshot in self._snapshots if snapshot.document_id == document_id]
        snapshots.sort(key=lambda snapshot: snapshot.created_at, reverse=True)
        return snapshots[:limit]


class TestSnapshotLineageService:
    @pytest.fixture
    def graph(self):
        document_id = uuid4()
        a = FakeSnapshot(uuid4(), document_id, None, datetime(2026, 5, 1, tzinfo=timezone.utc))
        b = FakeSnapshot(uuid4(), document_id, a.id, datetime(2026, 5, 2, tzinfo=timezone.utc))
        c = FakeSnapshot(uuid4(), document_id, b.id, datetime(2026, 5, 3, tzinfo=timezone.utc))
        d = FakeSnapshot(uuid4(), document_id, a.id, datetime(2026, 5, 2, tzinfo=timezone.utc) + timedelta(hours=1))
        e = FakeSnapshot(uuid4(), document_id, d.id, datetime(2026, 5, 4, tzinfo=timezone.utc))
        return document_id, [a, b, c, d, e]

    @pytest.fixture
    def service(self, graph):
        _, snapshots = graph
        return SnapshotLineageService(FakeSnapshotRepository(snapshots))

    @pytest.mark.asyncio
    async def test_get_ancestors_and_branch(self, service, graph):
        _, snapshots = graph
        a, b, c, _, _ = snapshots

        ancestors = await service.get_ancestors(None, c.id)
        branch = await service.get_branch(None, c.id)

        assert [snapshot.id for snapshot in ancestors] == [a.id, b.id]
        assert [snapshot.id for snapshot in branch.root_to_snapshot] == [a.id, b.id, c.id]

    @pytest.mark.asyncio
    async def test_get_descendants_and_branch_heads(self, service, graph):
        document_id, snapshots = graph
        a, b, c, d, e = snapshots

        descendants = await service.get_descendants(None, a.id)
        heads = await service.get_branch_heads(None, document_id)

        assert [snapshot.id for snapshot in descendants] == [b.id, d.id, c.id, e.id]
        assert {snapshot.id for snapshot in heads} == {c.id, e.id}

    @pytest.mark.asyncio
    async def test_find_common_ancestor(self, service, graph):
        _, snapshots = graph
        a, _, c, d, e = snapshots

        common = await service.find_common_ancestor(None, c.id, e.id)

        assert common is not None
        assert common.id == a.id
