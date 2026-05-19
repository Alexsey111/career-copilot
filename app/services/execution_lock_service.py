"""Redis-backed lock for pipeline execution workers."""

from __future__ import annotations

from uuid import UUID

from redis.asyncio import Redis

LOCK_TTL_MS = 10 * 60 * 1000


class ExecutionLockService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def acquire(self, execution_id: UUID) -> bool:
        key = self._key(execution_id)
        result = await self._redis.set(
            key,
            "1",
            nx=True,
            px=LOCK_TTL_MS,
        )
        return bool(result)

    async def release(self, execution_id: UUID) -> None:
        await self._redis.delete(self._key(execution_id))

    @staticmethod
    def _key(execution_id: UUID) -> str:
        return f"pipeline:execution:lock:{execution_id}"
