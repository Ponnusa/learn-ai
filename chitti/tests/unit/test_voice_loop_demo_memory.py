"""Unit tests for voice_loop_demo.py's session-summarization and
welcome-back-greeting helpers (decision 0018) -- real
ConversationService + MemoryRepository, fake LLM/tts/audio stand-ins,
no real API calls or hardware needed.
"""
import asyncio
from datetime import date, datetime, timedelta, timezone

from companion_robot.conversation.service import ConversationService
from companion_robot.memory.repository import MemoryRepository
from companion_robot.memory.schema import (
    ConsentStatus,
    MemoryCategory,
    MemoryRecord,
    MemorySource,
)
from companion_robot.parent_controls.profiles import ChildProfile, ChildProfileRepository
from companion_robot.storage.sqlite import connect
from companion_robot.voice.interfaces import LanguageModelBackend
from companion_robot.voice_loop_demo import _maybe_greet_with_recap, _summarize_and_remember_session


class _FakeLLM(LanguageModelBackend):
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[list[dict], str]] = []

    async def generate_reply(self, messages, system_prompt):
        self.calls.append((messages, system_prompt))
        return self.reply, "fake-model"


class _RaisingLLM(LanguageModelBackend):
    """Simulates a call that fails -- a second, impatient Ctrl-C
    cancelling the in-flight Claude call (decision 0021), or any other
    failure (bad API key, network error)."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def generate_reply(self, messages, system_prompt):
        raise self.exc


class _FakeAudio:
    def __init__(self) -> None:
        self.played: list[bytes] = []

    async def play(self, audio_bytes: bytes) -> None:
        self.played.append(audio_bytes)


class _FakeTTS:
    def __init__(self) -> None:
        self.synthesized: list[tuple[str, float]] = []

    async def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        self.synthesized.append((text, speed))
        return b"fake-audio"


def _make_memories() -> MemoryRepository:
    return MemoryRepository(connect(":memory:"))


def _make_profiles() -> ChildProfileRepository:
    return ChildProfileRepository(connect(":memory:"))


def _make_profile(profile_id: str = "p1", name: str = "Anna", **kwargs) -> ChildProfile:
    now = datetime.now(timezone.utc)
    return ChildProfile(id=profile_id, name=name, age=7, created_at=now, updated_at=now, **kwargs)


def _make_summary_record(record_id: str, content: str, created_at: datetime) -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        child_profile_id="p1",
        category=MemoryCategory.DAILY_SUMMARY,
        content=content,
        created_at=created_at,
        updated_at=created_at,
        source=MemorySource.SYSTEM_INFERRED,
        consent_or_authorization_status=ConsentStatus.GRANTED,
        retention_policy="demo",
    )


async def test_summarize_and_remember_session_writes_daily_summary():
    memories = _make_memories()
    summarizer = _FakeLLM(reply="Learned addition. Read a story about a fox.")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)
    messages = [
        {"role": "user", "content": "2 plus 2 is 4"},
        {"role": "assistant", "content": "Wow, neat!"},
    ]

    await _summarize_and_remember_session(conversation, memories, "p1", messages)

    records = memories.list_for_child("p1", category=MemoryCategory.DAILY_SUMMARY)
    assert len(records) == 1
    assert records[0].content == "Learned addition. Read a story about a fox."


async def test_summarize_and_remember_session_skips_empty_transcript():
    memories = _make_memories()
    summarizer = _FakeLLM(reply="should never be used")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)

    await _summarize_and_remember_session(conversation, memories, "p1", [])

    assert summarizer.calls == []
    assert memories.list_for_child("p1", category=MemoryCategory.DAILY_SUMMARY) == []


async def test_summarize_and_remember_session_skips_nothing_worth_keeping():
    memories = _make_memories()
    summarizer = _FakeLLM(reply="NOTHING")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)

    await _summarize_and_remember_session(
        conversation, memories, "p1", [{"role": "user", "content": "hi"}]
    )

    assert memories.list_for_child("p1", category=MemoryCategory.DAILY_SUMMARY) == []


async def test_summarize_and_remember_session_survives_cancellation(capsys):
    """A second, impatient Ctrl-C during the Claude call (decision
    0021) must not crash the program or leave the session half-saved
    -- just a clean message and no record."""
    memories = _make_memories()
    summarizer = _RaisingLLM(asyncio.CancelledError())
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)

    await _summarize_and_remember_session(
        conversation, memories, "p1", [{"role": "user", "content": "hi"}]
    )

    assert memories.list_for_child("p1", category=MemoryCategory.DAILY_SUMMARY) == []
    assert "interrupted" in capsys.readouterr().out


async def test_summarize_and_remember_session_survives_other_failures(capsys):
    """Any other failure (bad API key, network error) during the save
    should end the session cleanly too, not crash it."""
    memories = _make_memories()
    summarizer = _RaisingLLM(RuntimeError("boom"))
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)

    await _summarize_and_remember_session(
        conversation, memories, "p1", [{"role": "user", "content": "hi"}]
    )

    assert memories.list_for_child("p1", category=MemoryCategory.DAILY_SUMMARY) == []
    assert "couldn't save" in capsys.readouterr().out


async def test_summarize_and_remember_session_includes_story_title_in_transcript():
    """Found live (decision 0022): Story Companion's `messages` only
    ever held the story's body text, never its title, so the
    summarizer had no way to name which story a discussion was about."""
    memories = _make_memories()
    summarizer = _FakeLLM(reply="Discussed the story.")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)
    messages = [
        {"role": "assistant", "content": "Once there was a clever fox."},
        {"role": "user", "content": "What was the fox like?"},
    ]

    await _summarize_and_remember_session(
        conversation, memories, "p1", messages, story_title="The Clever Fox"
    )

    sent_transcript = summarizer.calls[0][0][0]["content"]
    assert "The Clever Fox" in sent_transcript


async def test_maybe_greet_with_recap_speaks_greeting_from_latest_summary():
    memories = _make_memories()
    memories.create(_make_summary_record("s1", "Learned addition.", datetime.now(timezone.utc)))
    profiles = _make_profiles()
    profile = _make_profile()
    profiles.create(profile)
    summarizer = _FakeLLM(reply="Hi Anna! Last time we learned addition!")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)
    tts = _FakeTTS()
    audio = _FakeAudio()

    await _maybe_greet_with_recap(conversation, tts, audio, memories, profiles, profile, 1.0)

    assert tts.synthesized[0][0] == "Hi Anna! Last time we learned addition!"
    assert len(audio.played) == 1


async def test_maybe_greet_with_recap_silent_on_first_session():
    memories = _make_memories()
    profiles = _make_profiles()
    profile = _make_profile()
    profiles.create(profile)
    summarizer = _FakeLLM(reply="should never be called")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)
    tts = _FakeTTS()
    audio = _FakeAudio()

    await _maybe_greet_with_recap(conversation, tts, audio, memories, profiles, profile, 1.0)

    assert tts.synthesized == []
    assert audio.played == []
    assert summarizer.calls == []


async def test_maybe_greet_with_recap_uses_the_most_recent_summary():
    memories = _make_memories()
    now = datetime.now(timezone.utc)
    memories.create(_make_summary_record("old", "Old summary.", now - timedelta(days=2)))
    memories.create(_make_summary_record("new", "New summary.", now - timedelta(days=1)))
    profiles = _make_profiles()
    profile = _make_profile()
    profiles.create(profile)
    summarizer = _FakeLLM(reply="greeting")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)
    tts = _FakeTTS()
    audio = _FakeAudio()

    await _maybe_greet_with_recap(conversation, tts, audio, memories, profiles, profile, 1.0)

    # build_welcome_back_prompt() embeds the summary in what's passed
    # as the system_prompt -- confirms the NEWER record was used.
    _, system_prompt = summarizer.calls[0]
    assert "New summary." in system_prompt
    assert "Old summary." not in system_prompt


async def test_maybe_greet_with_recap_skips_if_already_greeted_today():
    """Decision 0108: the actual fix -- restarting the demo again
    the same day must not re-run the greeting's own LLM call."""
    memories = _make_memories()
    memories.create(_make_summary_record("s1", "Learned addition.", datetime.now(timezone.utc)))
    profiles = _make_profiles()
    profile = _make_profile(last_greeted_date=date.today().isoformat())
    profiles.create(profile)
    summarizer = _FakeLLM(reply="should never be called")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)
    tts = _FakeTTS()
    audio = _FakeAudio()

    await _maybe_greet_with_recap(conversation, tts, audio, memories, profiles, profile, 1.0)

    assert tts.synthesized == []
    assert audio.played == []
    assert summarizer.calls == []


async def test_maybe_greet_with_recap_marks_the_profile_greeted_today_after_speaking():
    memories = _make_memories()
    memories.create(_make_summary_record("s1", "Learned addition.", datetime.now(timezone.utc)))
    profiles = _make_profiles()
    profile = _make_profile()  # last_greeted_date="" -- never greeted
    profiles.create(profile)
    summarizer = _FakeLLM(reply="Hi Anna!")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)

    await _maybe_greet_with_recap(conversation, _FakeTTS(), _FakeAudio(), memories, profiles, profile, 1.0)

    assert profiles.get(profile.id).last_greeted_date == date.today().isoformat()
