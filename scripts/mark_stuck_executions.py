from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import AsyncSessionLocal
from app.repositories.pipeline_repository import SQLAlchemyAsyncPipelineRepository
from app.services.pipeline_execution_service import PipelineExecutionService
from app.services.stuck_execution_service import StuckExecutionService


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold-minutes", type=int, default=30)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    async with AsyncSessionLocal() as session:
        repository = SQLAlchemyAsyncPipelineRepository(session)
        pipeline_service = PipelineExecutionService(repository)
        stuck_service = StuckExecutionService(
            pipeline_service=pipeline_service,
            threshold_minutes=args.threshold_minutes,
        )

        marked_count = await stuck_service.mark_stuck_executions_failed(
            limit=args.limit,
        )
        await session.commit()

    logging.info("Marked stuck executions failed: %s", marked_count)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
