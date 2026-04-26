# scripts\import_analyze_vacancy_utf8.py

from __future__ import annotations

import json
import sys

import httpx


API_BASE_URL = "http://localhost:8000/api/v1"


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    configure_stdout()

    payload = {
        "source": "manual",
        "title": "Backend Developer",
        "company": "Test Company",
        "location": "Remote",
        "description_raw": (
            "Требования:\n"
            "- Python\n"
            "- FastAPI\n"
            "- PostgreSQL\n"
            "\n"
            "Будет плюсом:\n"
            "- Redis\n"
            "- Docker\n"
        ),
    }

    with httpx.Client(timeout=30) as client:
        import_response = client.post(
            f"{API_BASE_URL}/vacancies/import",
            json=payload,
        )
        import_response.raise_for_status()
        vacancy = import_response.json()
        vacancy_id = vacancy["vacancy_id"]

        get_response = client.get(f"{API_BASE_URL}/vacancies/{vacancy_id}")
        get_response.raise_for_status()
        saved_vacancy = get_response.json()

        analyze_response = client.post(f"{API_BASE_URL}/vacancies/{vacancy_id}/analyze")
        analyze_response.raise_for_status()
        analysis = analyze_response.json()

    print("VACANCY")
    print(json.dumps(vacancy, ensure_ascii=False, indent=2))

    print("\nSAVED DESCRIPTION")
    print(saved_vacancy["description_raw"])

    print("\nANALYSIS")
    print(json.dumps(analysis, ensure_ascii=False, indent=2))

    print("\nMUST HAVE")
    for item in analysis["must_have"]:
        print("-", item["text"])

    print("\nNICE TO HAVE")
    for item in analysis["nice_to_have"]:
        print("-", item["text"])

    print("\nMATCH SCORE")
    print(analysis["match_score"])


if __name__ == "__main__":
    main()