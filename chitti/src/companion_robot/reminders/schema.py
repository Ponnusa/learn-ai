"""Reminder record schema (spec section 8).

Recurrence advances scheduled_at to the next occurrence after firing,
rather than tracking a separate last-fired timestamp -- a one-time
reminder (recurrence=None) is instead disabled after firing, which is
this schema's version of spec section 8's "expiration."
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ReminderSource(str, Enum):
    CHILD = "child"
    PARENT = "parent"


class Recurrence(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class ReminderRecord:
    """scheduled_at must be timezone-aware -- it carries both "scheduled
    time and time zone" from spec section 8 in one field. For a
    recurring reminder, tzinfo should be a zoneinfo.ZoneInfo (a real
    IANA zone, e.g. ZoneInfo("Europe/Helsinki")), not a fixed UTC
    offset -- that's what lets repository.py's recurrence advancement
    correctly handle daylight-saving transitions (spec section 8:
    "handle ... daylight-saving changes")."""

    id: str
    child_profile_id: str
    text: str
    scheduled_at: datetime
    source: ReminderSource
    created_at: datetime
    updated_at: datetime
    enabled: bool = True
    recurrence: Recurrence | None = None
    is_alarm: bool = False
