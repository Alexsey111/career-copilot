# app\domain\application_reminders.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


ReminderType = Literal[
    "draft_stale",
    "ready_not_submitted",
    "follow_up_missing",
]


@dataclass(slots=True)
class ApplicationReminder:
    application_id: UUID
    reminder_type: ReminderType
    title: str
    description: str
    days_since_event: int
    created_at: datetime
