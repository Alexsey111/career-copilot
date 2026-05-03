# scripts\debug_vacancy_analysis_parser.py

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.services.vacancy_analysis_service import (
    NICE_TO_HAVE_START_HEADINGS,
    REQUIREMENT_START_HEADINGS,
    STOP_HEADINGS,
    VacancyAnalysisService,
)


DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://career_user:career_pass@localhost:5432/career_copilot"
)


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _to_psycopg_url(database_url: str) -> str:
    url = make_url(database_url)

    if url.drivername == "postgresql":
        return str(url.set(drivername="postgresql+psycopg"))

    if url.drivername == "postgresql+psycopg":
        return str(url.set(drivername="postgresql+psycopg"))

    return database_url


async def load_vacancy_description(
    *,
    database_url: str,
    vacancy_id: UUID,
) -> str:
    engine = create_async_engine(_to_psycopg_url(database_url), future=True)

    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT description_raw
                    FROM vacancies
                    WHERE id = :vacancy_id
                    """
                ),
                {"vacancy_id": vacancy_id},
            )
            value = result.scalar_one_or_none()

            if value is None:
                raise RuntimeError(f"vacancy not found: {vacancy_id}")

            return value
    finally:
        await engine.dispose()


async def main() -> None:
    _configure_stdout()

    parser = argparse.ArgumentParser()
    parser.add_argument("vacancy_id", type=UUID)
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    args = parser.parse_args()

    service = VacancyAnalysisService()

    print("SERVICE FILE")
    print("-" * 80)
    print(Path(VacancyAnalysisService.__module__.replace(".", "/") + ".py"))
    print()

    description = await load_vacancy_description(
        database_url=args.database_url,
        vacancy_id=args.vacancy_id,
    )

    print("RAW DESCRIPTION REPR")
    print("-" * 80)
    print(repr(description))
    print()

    print("RAW DESCRIPTION PLAIN")
    print("-" * 80)
    print(description)
    print()

    lines = service._clean_lines(description)

    print("CLEAN LINES")
    print("-" * 80)
    for idx, line in enumerate(lines, start=1):
        print(f"{idx:02d}: {repr(line)} -> heading={service._normalize_heading(line)!r}")
    print()

    must_have = service._extract_section_items(
        lines,
        start_headings=REQUIREMENT_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )
    nice_to_have = service._extract_section_items(
        lines,
        start_headings=NICE_TO_HAVE_START_HEADINGS,
        stop_headings=STOP_HEADINGS,
    )
    fallback = service._fallback_requirement_candidates(lines)
    keywords = service._extract_keywords("Backend Developer", description)

    print("PARSED RESULT BY LOCAL CODE")
    print("-" * 80)
    print(f"must_have:    {must_have}")
    print(f"nice_to_have: {nice_to_have}")
    print(f"fallback:     {fallback}")
    print(f"keywords:     {keywords}")


if __name__ == "__main__":
    asyncio.run(main())
