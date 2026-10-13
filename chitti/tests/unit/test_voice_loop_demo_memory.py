"""Unit tests for voice_loop_demo.py's session-summarization and
welcome-back-greeting helpers (decision 0018) -- real
ConversationService + MemoryRepository, fake LLM/tts/audio stand-ins,
no real API calls or hardware needed.
"""
from datetime import datetime, timedelta, timezone

from companion_robot.conversation.service import ConversationService
from companion_robot.memory.repository import MemoryRepository
from companion_robot.memory.schema import (
    ConsentStatus,
    MemoryCategory,
    MemoryRecord,
    MemorySource,
)
from companion_robot.parent_controls.profiles import ChildProfile
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


def _make_profile(profile_id: str = "p1", name: str = "Anna") -> ChildProfile:
    now = datetime.now(timezone.utc)
    return ChildProfile(id=profile_id, name=name, age=7, created_at=now, updated_at=now)


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


async def test_maybe_greet_with_recap_speaks_greeting_from_latest_summary():
    memories = _make_memories()
    memories.create(_make_summary_record("s1", "Learned addition.", datetime.now(timezone.utc)))
    summarizer = _FakeLLM(reply="Hi Anna! Last time we learned addition!")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)
    tts = _FakeTTS()
    audio = _FakeAudio()

    await _maybe_greet_with_recap(conversation, tts, audio, memories, _make_profile(), 1.0)

    assert tts.synthesized[0][0] == "Hi Anna! Last time we learned addition!"
    assert len(audio.played) == 1


async def test_maybe_greet_with_recap_silent_on_first_session():
    memories = _make_memories()
    summarizer = _FakeLLM(reply="should never be called")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)
    tts = _FakeTTS()
    audio = _FakeAudio()

    await _maybe_greet_with_recap(conversation, tts, audio, memories, _make_profile(), 1.0)

    assert tts.synthesized == []
    assert audio.played == []
    assert summarizer.calls == []


async def test_maybe_greet_with_recap_uses_the_most_recent_summary():
    memories = _make_memories()
    now = datetime.now(timezone.utc)
    memories.create(_make_summary_record("old", "Old summary.", now - timedelta(days=2)))
    memories.create(_make_summary_record("new", "New summary.", now - timedelta(days=1)))
    summarizer = _FakeLLM(reply="greeting")
    conversation = ConversationService(_FakeLLM(reply="unused"), summarizer_llm=summarizer)
    tts = _FakeTTS()
    audio = _FakeAudio()

    await _maybe_greet_with_recap(conversation, tts, audio, memories, _make_profile(), 1.0)

    # build_welcome_back_prompt() embeds the summary in what's passed
    # as the system_prompt -- confirms the NEWER record was used.
    _, system_prompt = summarizer.calls[0]
    assert "New summary." in system_prompt
    assert "Old summary." not in system_prompt
