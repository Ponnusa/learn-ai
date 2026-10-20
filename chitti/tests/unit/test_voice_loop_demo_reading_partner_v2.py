"""Unit tests for Reading Partner v2 (decision 0075) --
voice_loop_demo._run_reading_partner_v2(). Real ConversationService/
repositories, fake LLM/tts/audio/stt/face stand-ins, no real API
calls, hardware, or keyboard input() needed. Deliberately a separate
test file from test_voice_loop_demo_intent.py's (which covers the
original _run_reading_partner()), matching the two flows' own
separation -- v1's tests are untouched by this file.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from companion_robot.conversation.service import ConversationService
from companion_robot.device.interfaces import DeviceState
from companion_robot.parent_controls.reading_exercises import (
    ReadingExerciseRecord,
    ReadingExerciseRepository,
)
from companion_robot.reading.repository import ReadingRepository
from companion_robot.storage.sqlite import connect
from companion_robot.voice.interfaces import LanguageModelBackend
from companion_robot.voice_loop_demo import _run_reading_partner_v2


@pytest.fixture(autouse=True)
def _reading_exercises_enabled(monkeypatch):
    monkeypatch.setenv("CHITTI_ENABLE_READING_EXERCISES", "1")


class _FakeLLM(LanguageModelBackend):
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[list[dict], str]] = []

    async def generate_reply(self, messages, system_prompt):
        self.calls.append((messages, system_prompt))
        return self.reply, "fake-model"


class _FakeAudio:
    async def play(self, audio_bytes: bytes) -> None:
        pass

    async def stop_playback(self) -> None:
        pass


class _FakeTTS:
    def __init__(self) -> None:
        self.synthesized: list[str] = []

    async def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        self.synthesized.append(text)
        return b"fake-audio"


class _FakeFace:
    def __init__(self) -> None:
        self.states: list[DeviceState] = []
        self.modes: list[str | None] = []
        self.reading_texts: list[list[str] | None] = []
        self.spotlights: list[str | None] = []

    def set_status_led(self, state: DeviceState) -> None:
        self.states.append(state)

    def set_expression_mode(self, mode: str | None) -> None:
        self.modes.append(mode)

    def set_reading_text(
        self, lines: list[str] | None, *, wpm: float = 45.0, font_size: int = 28,
        font_color: str = "white",
    ) -> None:
        self.reading_texts.append(lines)

    def set_reading_spotlight(self, word: str | None) -> None:
        self.spotlights.append(word)


def _make_exercise(conn, content: str, title: str = "Homework"):
    reading_exercises = ReadingExerciseRepository(conn)
    reading_exercises.create(
        ReadingExerciseRecord(
            id="ex1",
            child_profile_id="child-1",
            title=title,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
    )
    return reading_exercises


async def test_clean_first_read_skips_straight_to_comprehension():
    """Decision 0075's core adaptive rule: a child who reads well on
    the first try is praised and moved straight to the understanding
    check -- no model, no together-read, no word practice."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = _make_exercise(conn, "A cat sat.")
    llm = _FakeLLM(reply="Sorry, no questions.")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        # V2 has no word game (decision 0057) between comprehension
        # and "want another one?" -- unlike v1, this is the direct
        # answer to that prompt.
        side_effect=["a cat sat", "let's just chat"],
    ):
        next_mode, carried_text = await _run_reading_partner_v2(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "Wow, you read that all by yourself!" in tts.synthesized
    assert "Listen to me first. Follow the words with your eyes!" not in tts.synthesized
    assert "Let's read the whole sentence one more time." not in tts.synthesized


async def test_rough_read_goes_through_model_together_and_second_attempt():
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = _make_exercise(conn, "A cat sat.")
    llm = _FakeLLM(reply="Sorry, no questions.")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=[
            "a dog ran",  # first attempt -- way off
            "a cat ran",  # the supported "together" read
            "a cat sat",  # the second, independent attempt -- clean this time
            "let's just chat",
        ],
    ):
        next_mode, carried_text = await _run_reading_partner_v2(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "Listen to me first. Follow the words with your eyes!" in tts.synthesized
    assert "Now let's read it together. Ready? Let's go!" in tts.synthesized
    assert "Lovely! Now it's your turn. See if you can read it all by yourself." in tts.synthesized
    # The second attempt was clean -- no real misses left, so word
    # practice and the final reread are both skipped.
    assert not any("practise" in line.lower() for line in tts.synthesized)
    assert "Let's read the whole sentence one more time." not in tts.synthesized


async def test_word_practice_runs_for_a_still_difficult_word_then_rereads():
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = _make_exercise(conn, "A cat sat.")
    llm = _FakeLLM(reply="Sorry, no questions.")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=[
            "a dog ran",  # first attempt -- way off
            "a cat ran",  # the supported "together" read
            "a cat mat",  # second attempt -- "sat" still missed
            "sat",  # repeats "sat" right after Chitti models it (echo)
            "sat",  # tries "sat" again, independently this time
            "a cat sat",  # the final whole-sentence reread
            "let's just chat",
        ],
    ):
        next_mode, carried_text = await _run_reading_partner_v2(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert any("practise" in line.lower() for line in tts.synthesized)
    assert 'Listen to Chitti say the word: "sat".' in tts.synthesized
    assert "Let's read the whole sentence one more time." in tts.synthesized
    assert face.spotlights[0] == "sat"
    assert None in face.spotlights  # cleared after practice


async def test_help_request_on_first_attempt_skips_straight_to_modeling():
    """An empty/explicit-help capture is never graded as a bad read."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = _make_exercise(conn, "A cat sat.")
    llm = _FakeLLM(reply="Sorry, no questions.")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=[
            "read with me",  # an explicit help request, not an attempt
            "a cat ran",  # the supported "together" read
            "a cat sat",  # the second, independent attempt -- clean
            "let's just chat",
        ],
    ):
        next_mode, carried_text = await _run_reading_partner_v2(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "No worries! Let me show you how." in tts.synthesized
    assert "Wow, you read that all by yourself!" not in tts.synthesized
    profile = reading.get_or_create("child-1")
    # The help request itself never touched mastery -- only the
    # second, independent attempt did.
    assert profile.sessions_completed == 1


async def test_stopping_mid_session_ends_warmly_without_comprehension():
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = _make_exercise(conn, "A cat sat.")
    llm = _FakeLLM(reply="unused -- must never be reached")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=[
            "a dog ran",  # first attempt -- way off
            "this is too hard, I'm done",  # stops during the together read
        ],
    ):
        next_mode, carried_text = await _run_reading_partner_v2(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode is None
    assert "That's okay, we can try more another time! Great effort today." in tts.synthesized
    assert not any("QUESTION" in line for line in tts.synthesized)
    assert llm.calls == []  # comprehension is never reached


async def test_comprehension_question_is_asked_and_reacted_to():
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = _make_exercise(conn, "A cat sat.")
    llm = _FakeLLM(reply="unused")
    llm.generate_reply = AsyncMock(
        side_effect=[
            ("QUESTION: Who sat down?", "fake-model"),
            ("STATUS: resolved\nSAY: Yes, the cat!", "fake-model"),
        ]
    )
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=["a cat sat", "the cat", "let's just chat"],
    ):
        next_mode, carried_text = await _run_reading_partner_v2(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode == "3"
    assert "Who sat down?" in tts.synthesized
    assert "Yes, the cat!" in tts.synthesized


async def test_v1_and_v2_use_the_same_reading_profile():
    """Mastery is a shared fact regardless of which flow taught it --
    v2 updates the same ReadingProfile v1 does."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = _make_exercise(conn, "A cat sat.")
    llm = _FakeLLM(reply="Sorry, no questions.")
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=["a cat sat", "let's just chat"],
    ):
        await _run_reading_partner_v2(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    profile = reading.get_or_create("child-1")
    assert profile.sessions_completed == 1
    assert profile.masteries["a"].opportunities > 0


async def test_falls_back_to_the_deterministic_builder_when_generation_fails():
    """Decision 0077: when LLM book generation fails, v2 falls back to
    the guaranteed-decodable, offline builder instead of apologizing
    with nothing to read."""
    conn = connect(":memory:")
    reading = ReadingRepository(conn)
    reading_exercises = _make_exercise(conn, "A cat sat.")
    llm = _FakeLLM(reply="unused")

    async def _always_fails(_messages, system_prompt):
        if "decodable" in system_prompt.lower() and "story" in system_prompt.lower():
            return "TITLE: Bad\nPAGE: A ship sat.", "fake-model"  # always undecodable
        return "Sorry, no questions.", "fake-model"

    llm.generate_reply = AsyncMock(side_effect=_always_fails)
    conversation = ConversationService(llm)
    face = _FakeFace()
    tts = _FakeTTS()

    # A function, not a fixed list: the fallback builder's own content
    # is deterministic word-practice text, not natural prose, so a
    # fixed "read it back" guess could easily read as a rough first
    # attempt and walk into model/together/second-read/practice --
    # an unpredictable number of extra captures. Answering with an
    # explicit stop request after the two known turns ends the
    # session cleanly and quickly however many turns v2's adaptive
    # flow would otherwise take.
    scripted = iter(["a cat sat", "yes please"])

    async def _capture_side_effect(*_args, **_kwargs):
        try:
            return next(scripted)
        except StopIteration:
            return "I'm done, this is too hard"

    with patch(
        "companion_robot.voice_loop_demo._capture_and_transcribe",
        new_callable=AsyncMock,
        side_effect=_capture_side_effect,
    ):
        next_mode, carried_text = await _run_reading_partner_v2(
            conversation, tts, _FakeAudio(), "fake-stt",
            reading, reading_exercises, face, "child-1", 1.0,
        )

    assert next_mode is None
    assert not any("having trouble coming up with a story" in line for line in tts.synthesized)
    # The session continued into a real sentence from the fallback
    # book (modeled, then stopped on request) instead of dead-ending.
    assert "Listen to me first. Follow the words with your eyes!" in tts.synthesized
    assert "That's okay, we can try more another time! Great effort today." in tts.synthesized
