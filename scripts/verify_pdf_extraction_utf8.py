# scripts\verify_pdf_extraction_utf8.py

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://career_user:career_pass@localhost:5432/career_copilot"
)


def _configure_stdout() -> None:
    # Helps on Windows, but saved UTF-8 files below are still the source of truth.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _to_psycopg_url(database_url: str) -> str:
    url = make_url(database_url)

    if url.drivername == "postgresql":
        return str(url.set(drivername="postgresql+psycopg"))

    if url.drivername == "postgresql+psycopg":
        return str(url.set(drivername="postgresql+psycopg"))

    return database_url


def _json_default(value: Any) -> str:
    return str(value)


def _safe_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _count_mojibake_markers(text_value: str) -> dict[str, int]:
    markers = ["Ð", "Ñ", "â", "�"]
    return {marker: text_value.count(marker) for marker in markers}


def upload_and_import_pdf(
    *,
    api_base_url: str,
    pdf_path: Path,
) -> dict[str, Any]:
    with httpx.Client(timeout=60) as client:
        with pdf_path.open("rb") as file_obj:
            upload_response = client.post(
                f"{api_base_url}/files/upload",
                data={"file_kind": "resume"},
                files={
                    "file": (
                        pdf_path.name,
                        file_obj,
                        "application/pdf",
                    )
                },
            )

        upload_response.raise_for_status()
        upload_payload = upload_response.json()
        source_file_id = upload_payload["id"]

        import_response = client.post(
            f"{api_base_url}/profile/import-resume",
            json={"source_file_id": source_file_id},
        )
        import_response.raise_for_status()

        return {
            "upload_response": upload_payload,
            "import_response": import_response.json(),
            "raw_import_response_text": import_response.text,
        }


async def load_extraction_row(
    *,
    database_url: str,
    extraction_id: UUID,
) -> dict[str, Any]:
    engine = create_async_engine(
        _to_psycopg_url(database_url),
        future=True,
    )

    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT
                        fe.id AS extraction_id,
                        fe.source_file_id,
                        fe.status,
                        fe.parser_name,
                        fe.parser_version,
                        fe.extracted_text,
                        fe.extracted_metadata_json,
                        fe.created_at,
                        sf.original_name,
                        sf.mime_type,
                        sf.size_bytes,
                        sf.storage_key
                    FROM file_extractions fe
                    JOIN source_files sf ON sf.id = fe.source_file_id
                    WHERE fe.id = :extraction_id
                    """
                ),
                {"extraction_id": extraction_id},
            )
            row = result.mappings().one_or_none()

            if row is None:
                raise RuntimeError(f"file_extractions row not found: {extraction_id}")

            return dict(row)
    finally:
        await engine.dispose()


def write_utf8_outputs(
    *,
    output_dir: Path,
    payload: dict[str, Any],
    db_row: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_text = db_row["extracted_text"]

    response_path = output_dir / "raw_import_response.json"
    db_row_path = output_dir / "db_row_without_full_text.json"
    extracted_text_path = output_dir / "db_extracted_text_utf8.txt"
    repr_path = output_dir / "db_extracted_text_repr.txt"

    response_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )

    db_row_light = {
        key: value
        for key, value in db_row.items()
        if key != "extracted_text"
    }
    db_row_light["text_length"] = len(extracted_text)
    db_row_light["line_count"] = len(extracted_text.splitlines())
    db_row_light["mojibake_markers"] = _count_mojibake_markers(extracted_text)

    db_row_path.write_text(
        json.dumps(db_row_light, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )

    extracted_text_path.write_text(extracted_text, encoding="utf-8")
    repr_path.write_text(repr(extracted_text[:2000]), encoding="utf-8")

    print()
    print("Saved diagnostic files:")
    print(f"  {response_path}")
    print(f"  {db_row_path}")
    print(f"  {extracted_text_path}")
    print(f"  {repr_path}")


def print_summary(
    *,
    payload: dict[str, Any],
    db_row: dict[str, Any],
) -> None:
    import_response = payload["import_response"]
    extracted_text = db_row["extracted_text"]

    print("PDF EXTRACTION UTF-8 DIAGNOSTIC")
    print("-" * 80)
    print(f"source_file_id:   {import_response['source_file_id']}")
    print(f"extraction_id:    {import_response['extraction_id']}")
    print(f"detected_format:  {import_response['detected_format']}")
    print(f"api_text_length:  {import_response['text_length']}")
    print(f"db_text_length:   {len(extracted_text)}")
    print(f"db_line_count:    {len(extracted_text.splitlines())}")
    print(f"original_name:    {db_row['original_name']}")
    print(f"mime_type:        {db_row['mime_type']}")
    print(f"parser_name:      {db_row['parser_name']}")
    print(f"parser_version:   {db_row['parser_version']}")
    print(f"metadata:         {db_row['extracted_metadata_json']}")
    print(f"markers:          {_count_mojibake_markers(extracted_text)}")
    print("-" * 80)
    print("API preview repr:")
    print(repr(import_response.get("text_preview", "")[:500]))
    print("-" * 80)
    print("DB extracted_text repr:")
    print(repr(extracted_text[:500]))
    print("-" * 80)
    print("DB extracted_text plain preview:")
    print(extracted_text[:1000])


async def main() -> None:
    _configure_stdout()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to a real PDF resume file.",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL),
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    pdf_path: Path = args.pdf_path
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    if pdf_path.suffix.lower() != ".pdf":
        raise RuntimeError(f"Expected .pdf file, got: {pdf_path}")

    payload = upload_and_import_pdf(
        api_base_url=args.api_base_url.rstrip("/"),
        pdf_path=pdf_path,
    )

    extraction_id = UUID(payload["import_response"]["extraction_id"])

    db_row = await load_extraction_row(
        database_url=args.database_url,
        extraction_id=extraction_id,
    )

    output_dir = args.output_dir
    if output_dir is None:
        output_dir = (
            Path("data")
            / "diagnostics"
            / f"pdf_extraction_{_safe_timestamp()}_{str(extraction_id)[:8]}"
        )

    write_utf8_outputs(
        output_dir=output_dir,
        payload=payload,
        db_row=db_row,
    )

    print_summary(
        payload=payload,
        db_row=db_row,
    )


if __name__ == "__main__":
    asyncio.run(main())
