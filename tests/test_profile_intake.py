from __future__ import annotations

import pytest


API_PREFIX = "/api/v1"
pytestmark = pytest.mark.asyncio


async def test_manual_profile_intake_builds_profile_and_evidence_bank(client) -> None:
    response = await client.post(
        f"{API_PREFIX}/profile/intake/manual",
        json={
            "personal": {
                "name": "Alex Perminov",
                "location": "Remote",
                "target_role": "AI Automation Specialist",
            },
            "skills": {
                "technologies": ["Python", "SQL"],
                "ai_tools": ["ChatGPT", "LLM"],
                "automation_tools": ["Make", "Zapier"],
            },
            "experience": [
                {
                    "company_or_project": "AI quality workflow",
                    "role": "Automation builder",
                    "what_did_you_do": "Built AI-assisted workflow for quality checks.",
                    "technologies": ["Python", "ChatGPT"],
                    "results": "Reduced manual review by 40%",
                }
            ],
            "projects": [
                {
                    "title": "Prompt Engineering Toolkit",
                    "description": "Reusable prompts for screening and analysis.",
                    "stack": ["ChatGPT", "LLM", "Python"],
                    "results": "Faster candidate review",
                }
            ],
            "education": [
                {
                    "title": "Computer Science basics",
                    "institution": "Self-study",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"] == "manual"
    assert payload["full_name"] == "Alex Perminov"
    assert payload["target_roles"][:1] == ["AI Automation Specialist"]
    assert payload["experience_count"] == 1
    assert payload["project_count"] == 1
    assert payload["achievement_count"] == 2
    assert payload["evidence_snippet_count"] >= 4
    assert "ChatGPT" in payload["ai_tools"]
    assert "GUIDED PROFILE INTAKE" in payload["raw_text_preview"]

    bank_response = await client.get(f"{API_PREFIX}/evidence/bank")
    assert bank_response.status_code == 200, bank_response.text
    bank = bank_response.json()
    titles = {item["title"] for item in bank["snippets"]}
    assert "AI quality workflow" in titles
    assert "Prompt Engineering Toolkit" in titles
    assert "AI tools" in titles
    assert bank["project_evidence"]
    assert bank["competency_signals"]


async def test_github_profile_intake_builds_project_evidence_without_pdf(client) -> None:
    response = await client.post(
        f"{API_PREFIX}/profile/intake/github",
        json={
            "username": "alex-ai",
            "profile_url": "https://github.com/alex-ai",
            "target_role": "Python Automation Developer",
            "repositories": [
                {
                    "name": "cv-automation",
                    "description": "Automation scripts for resume and vacancy matching.",
                    "stack": ["Python", "GitHub Actions", "LLM"],
                    "highlights": ["Parsed vacancy text", "Generated evidence summaries"],
                    "url": "https://github.com/alex-ai/cv-automation",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"] == "github"
    assert payload["target_roles"][:1] == ["Python Automation Developer"]
    assert payload["project_count"] == 1
    assert payload["evidence_snippet_count"] == 1
    assert "GITHUB PROFILE INTAKE" in payload["raw_text_preview"]

    bank_response = await client.get(f"{API_PREFIX}/evidence/bank")
    assert bank_response.status_code == 200, bank_response.text
    bank = bank_response.json()
    github_item = next(item for item in bank["project_evidence"] if item["title"] == "cv-automation")
    assert github_item["fact_status"] == "user_provided"
    assert "LLM" in github_item["skills"]
