"""Engagement session schema (decision 0023) -- plain behavioral
counts (how much the child spoke), not an evaluation of what they
said. Each session writes exactly one immutable row, same spirit as
a DAILY_SUMMARY memory record.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EngagementMode(str, Enum):
    TEACHABLE_FRIEND = "teachable_friend"
    STORY_COMPANION = "story_companion"


@dataclass
class EngagementSession:
    id: str
    child_profile_id: str
    mode: EngagementMode
    turn_count: int
    word_count: int
    created_at: datetime
