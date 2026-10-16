"""Unit tests for voice_loop_demo.py's _save_transcript() (decision
0038) -- plain formatting + storage, no LLM or audio involved.
"""
from datetime import datetime, timezone

from companion_robot.engagement.schema import EngagementMode
from companion_robot.storage.sqlite import connect
from companion_robot.transcripts.repository import TranscriptRepository
from companion_robot.voice_loop_demo import _save_transcript


def _make_repo() -> TranscriptRepository:
    return TranscriptRepository(connect(":memory:"))


def test_save_transcript_formats_the_full_session():
    transcripts = _make_repo()
    messages = [
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "I am bored"},
        {"role": "assistant", "content": "Let's play a game!"},
    ]

    _save_transcript(transcripts, "anna", EngagementMode.EVERYDAY_COMPANION, messages)

    records = transcripts.list_for_child("anna")
    assert len(records) == 1
    assert records[0].mode == EngagementMode.EVERYDAY_COMPANION
    assert records[0].content == (
        "assistant: Hi there!\nuser: I am bored\nassistant: Let's play a game!"
    )


def test_save_transcript_sets_an_expiry_in_the_future():
    transcripts = _make_repo()
    messages = [{"role": "user", "content": "hi"}]

    _save_transcript(transcripts, "anna", EngagementMode.TEACHABLE_FRIEND, messages)

    record = transcripts.list_for_child("anna")[0]
    assert record.expires_at is not None
    assert record.expires_at > datetime.now(timezone.utc)


def test_save_transcript_skips_an_empty_session():
    transcripts = _make_repo()

    _save_transcript(transcripts, "anna", EngagementMode.STORY_COMPANION, [])

    assert transcripts.list_for_child("anna") == []
