"""Unit tests for voice_loop_demo.py's engagement-tracking helper
(decision 0023) -- plain counting, no LLM or audio involved.
"""
from companion_robot.engagement.repository import EngagementRepository
from companion_robot.engagement.schema import EngagementMode
from companion_robot.storage.sqlite import connect
from companion_robot.voice_loop_demo import _record_engagement_session


def _make_repo() -> EngagementRepository:
    return EngagementRepository(connect(":memory:"))


def test_record_engagement_session_counts_only_child_turns():
    engagement = _make_repo()
    messages = [
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "Dogs can smell really well"},
        {"role": "assistant", "content": "Wow, tell me more!"},
        {"role": "user", "content": "They have a wet nose too"},
    ]

    _record_engagement_session(engagement, "anna", EngagementMode.TEACHABLE_FRIEND, messages)

    sessions = engagement.list_for_child("anna")
    assert len(sessions) == 1
    assert sessions[0].turn_count == 2
    assert sessions[0].word_count == 5 + 6  # "Dogs can smell really well" + "They have a wet nose too"
    assert sessions[0].mode == EngagementMode.TEACHABLE_FRIEND


def test_record_engagement_session_skips_a_session_with_no_child_turns():
    engagement = _make_repo()
    messages = [{"role": "assistant", "content": "Once upon a time..."}]

    _record_engagement_session(engagement, "anna", EngagementMode.STORY_COMPANION, messages)

    assert engagement.list_for_child("anna") == []
