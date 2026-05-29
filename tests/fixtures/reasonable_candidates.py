from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateFixture:
    kind: str
    text: str
    source_file_kind: str = "resume"


REASONABLE_CANDIDATE_FIXTURES = [
    CandidateFixture(
        kind="manager",
        text="""
Мария Иванова
ОПЫТ
1. Coordinated launch of a regional sales process and improved weekly reporting.
Навыки
planning, reporting, communication
""",
    ),
    CandidateFixture(
        kind="doctor",
        text="""
Dr. Sam Lee
EXPERIENCE
1. Reduced patient discharge delays by coordinating doctors, nurses and reception.
Skills
patient care, scheduling, documentation
""",
    ),
    CandidateFixture(
        kind="lawyer",
        text="""
Alex Morgan
ACHIEVEMENTS
1. Prepared legal claim templates and standardized case documentation.
Skills
contracts, compliance, writing
""",
    ),
    CandidateFixture(
        kind="student",
        text="""
Student Profile
PROJECTS
1. Built a class research dashboard with spreadsheet analysis and presentation.
Education
Bachelor program
""",
    ),
    CandidateFixture(
        kind="career_switch",
        text="""
Career Switcher
Portfolio
1. Customer Support Automation
Built FAQ workflow and reduced repetitive support replies.
Stack: no-code tools, spreadsheets.
""",
        source_file_kind="portfolio",
    ),
    CandidateFixture(
        kind="empty_profile",
        text="",
    ),
    CandidateFixture(
        kind="warehouse_worker",
        text="""
Warehouse Worker
ОПЫТ
1. Improved shelf picking route and reduced packing errors during peak shifts.
Навыки
inventory, safety, teamwork
""",
    ),
    CandidateFixture(
        kind="sales",
        text="""
Sales Specialist
ACHIEVEMENTS
1. Negotiated supplier contracts and improved monthly purchasing control.
Skills
crm, negotiation, reporting
""",
    ),
    CandidateFixture(
        kind="backend_engineer",
        text="""
Backend Engineer
PROJECTS
1. Implemented API integration with PostgreSQL and Docker-based deployment.
Skills
Python, FastAPI, PostgreSQL, Docker
""",
    ),
]
