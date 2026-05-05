import asyncio
from sqlalchemy import select
from app.db.session import get_db_session
from app.models.entities import AIRun

async def check():
    async for session in get_db_session():
        result = await session.execute(select(AIRun).order_by(AIRun.created_at.desc()).limit(5))
        rows = result.scalars().all()
        print(f"Found {len(rows)} AI runs:")
        for r in rows:
            print(f"ID: {r.id}")
            print(f"  workflow: {r.workflow_name}")
            print(f"  provider: {r.provider_name}")
            print(f"  model: {r.model_name}")
            print(f"  status: {r.status}")
            print()
        if not rows:
            print("No AI runs found in database.")
        break

asyncio.run(check())
