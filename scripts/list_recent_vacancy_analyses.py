# scripts\list_recent_vacancy_analyses.py

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


DATABASE_URL = "postgresql+psycopg://career_user:career_pass@localhost:5432/career_copilot"


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def json_default(value):
    if isinstance(value, (datetime, UUID, Decimal)):
        return str(value)
    return str(value)


async def main() -> None:
    configure_stdout()

    engine = create_async_engine(DATABASE_URL, future=True)

    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT
                            v.id,
                            v.title,
                            v.created_at,
                            v.description_raw,
                            va.must_have_json,
                            va.nice_to_have_json,
                            va.keywords_json,
                            va.strengths_json,
                            va.gaps_json,
                            va.match_score,
                            va.created_at AS analysis_created_at
                        FROM vacancies v
                        LEFT JOIN LATERAL (
                            SELECT *
                            FROM vacancy_analyses va
                            WHERE va.vacancy_id = v.id
                            ORDER BY va.created_at DESC
                            LIMIT 1
                        ) va ON true
                        ORDER BY v.created_at DESC
                        LIMIT 10
                        """
                    )
                )
            ).mappings().all()

        for row in rows:
            item = dict(row)

            print("=" * 100)
            print(f"vacancy_id:          {item['id']}")
            print(f"title:               {item['title']}")
            print(f"created_at:          {item['created_at']}")
            print(f"analysis_created_at: {item['analysis_created_at']}")
            print(f"match_score:         {item['match_score']}")

            print("\nmust_have_json:")
            print(json.dumps(item["must_have_json"], ensure_ascii=False, indent=2, default=json_default))

            print("\nnice_to_have_json:")
            print(json.dumps(item["nice_to_have_json"], ensure_ascii=False, indent=2, default=json_default))

            print("\nkeywords_json:")
            print(json.dumps(item["keywords_json"], ensure_ascii=False, indent=2, default=json_default))

            print("\nstrengths_json:")
            print(json.dumps(item["strengths_json"], ensure_ascii=False, indent=2, default=json_default))

            print("\ngaps_json:")
            print(json.dumps(item["gaps_json"], ensure_ascii=False, indent=2, default=json_default))

            print("\ndescription_raw repr:")
            print(repr(item["description_raw"]))

            print("\ndescription_raw plain:")
            print(item["description_raw"])

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
