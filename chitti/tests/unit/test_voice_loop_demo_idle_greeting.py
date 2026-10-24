"""Unit tests for voice_loop_demo.py's idle-greeting nudge (decision
0109) -- a fixed, generic line spoken the next time a mode is about
to wait for the child's next turn, if it's been at least 60 minutes
since the last one. No LLM call, no real hardware needed.
"""
from datetime import datetime, timedelta, timezone

import companion_robot.voice_loop_demo as voice_loop_demo
from companion_robot.voice_loop_demo import _idle_greeting_text, _maybe_speak_idle_greeting


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


class _FakeFace:
    def __init__(self) -> None:
        self.statuses: list = []

    def set_status_led(self, state) -> None:
        self.statuses.append(state)


def test_idle_greeting_text_includes_the_childs_name():
    assert (
        _idle_greeting_text("Anna")
        == "Hey Anna! I'm here if you want to read, play, or tell me something!"
    )


async def test_silent_on_the_very_first_call_ever(monkeypatch):
    """Nothing to measure a gap against yet -- same "silently does
    nothing" shape decision 0018/0108 already use for a first-ever
    session."""
    monkeypatch.setattr(voice_loop_demo, "_last_interaction_at", None)
    tts, audio, face = _FakeTTS(), _FakeAudio(), _FakeFace()

    await _maybe_speak_idle_greeting(tts, audio, face, 1.0, "Anna")

    assert tts.synthesized == []
    assert audio.played == []
    assert voice_loop_demo._last_interaction_at is not None  # clock now started


async def test_silent_within_the_60_minute_window(monkeypatch):
    monkeypatch.setattr(
        voice_loop_demo, "_last_interaction_at", datetime.now(timezone.utc) - timedelta(minutes=30)
    )
    tts, audio, face = _FakeTTS(), _FakeAudio(), _FakeFace()

    await _maybe_speak_idle_greeting(tts, audio, face, 1.0, "Anna")

    assert tts.synthesized == []
    assert audio.played == []


async def test_speaks_the_generic_greeting_after_60_minutes_idle(monkeypatch):
    monkeypatch.setattr(
        voice_loop_demo, "_last_interaction_at", datetime.now(timezone.utc) - timedelta(minutes=61)
    )
    tts, audio, face = _FakeTTS(), _FakeAudio(), _FakeFace()

    await _maybe_speak_idle_greeting(tts, audio, face, 1.0, "Anna")

    assert tts.synthesized == [
        ("Hey Anna! I'm here if you want to read, play, or tell me something!", 1.0)
    ]
    assert len(audio.played) == 1


async def test_does_not_repeat_itself_right_after_speaking(monkeypatch):
    monkeypatch.setattr(
        voice_loop_demo, "_last_interaction_at", datetime.now(timezone.utc) - timedelta(minutes=61)
    )
    tts, audio, face = _FakeTTS(), _FakeAudio(), _FakeFace()

    await _maybe_speak_idle_greeting(tts, audio, face, 1.0, "Anna")
    await _maybe_speak_idle_greeting(tts, audio, face, 1.0, "Anna")

    assert len(tts.synthesized) == 1
    assert len(audio.played) == 1
