from app.services.resume_generation_service import ResumeGenerationService
from app.services.resume_renderer import render_resume


def test_resume_generation_extracts_and_renders_contacts() -> None:
    service = ResumeGenerationService()

    raw_text = """
John Doe
john.doe@example.com
+7 999 123-45-67
https://github.com/johndoe/
@johndoe_dev
"""

    contacts = service._extract_contact_info(raw_text)

    rendered = render_resume(
        {
            "candidate": {
                "full_name": "John Doe",
                "headline": "Backend Developer",
                "location": "Remote",
                "contacts": contacts,
            },
            "target_vacancy": {
                "title": "Backend Developer",
            },
            "sections": {
                "summary_bullets": ["Python, FastAPI, PostgreSQL"],
                "skills": ["Python", "FastAPI"],
                "experience": [],
                "selected_achievements": [],
                "relevant_to_vacancy": [],
                "competency_mapping": [],
            },
        }
    )

    assert contacts["email"] == "john.doe@example.com"
    assert contacts["phone"] == "+7 999 123-45-67"
    assert contacts["github"] == "https://github.com/johndoe"
    assert contacts["telegram"] == "@johndoe_dev"

    assert "john.doe@example.com" in rendered
    assert "https://github.com/johndoe" in rendered
    assert "+7 999 123-45-67" in rendered

