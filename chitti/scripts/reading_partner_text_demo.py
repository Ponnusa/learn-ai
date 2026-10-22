#!/usr/bin/env python
"""Text-only Reading Partner harness -- no voice, no screen. Lets the
whole Reading Partner use case (parent-uploaded exercises, the hint
ladder, mastery tracking, comprehension questions, the word game,
word-family practice, re-reads, themed follow-ups) be exercised end to
end by TYPING what the child would say, with a real LLM backend and
the real parental-control data -- the same ReadingRepository/
ReadingExerciseRepository/ChildProfileRepository, against the same
chitti/data/chitti.db the Parent Controls web UI reads from -- before
wiring any of this back to real audio/screen hardware.

Reuses _run_reading_partner() completely unmodified: the only two call
sites that normally touch real audio
(voice_loop_demo._capture_and_transcribe / _speak) are monkeypatched
here to read a line from stdin / print a line to stdout instead, the
same technique this project's own test suite already uses. Every
other decision this mode has ever shipped (BKT mastery, miscue
alignment, the hint ladder, word-family verification, sentence-by-
sentence resume, etc.) runs exactly as it does on real hardware --
nothing about the reading logic itself is faked, only the two literal
audio I/O points. The screen is skipped the same way
CHITTI_DISABLE_FACE already does on real hardware: a real, unstarted
ScreenFaceDeviceController, whose set_status_led()/set_reading_text()/
set_reading_spotlight() calls are harmless no-ops when its render
thread was never started -- no separate fake-face class needed.

Requires OPENAI_API_KEY in chitti/.env (same as voice_loop_demo.py).

Decision 0075: set CHITTI_READING_PARTNER_V2=1 to exercise the new,
separate model/together/independent/practice flow instead -- same
toggle voice_loop_demo.py's own mode dispatch uses, so this harness
tests whichever version is actually configured.

Usage: python scripts/reading_partner_text_demo.py
"""
import asyncio
import os
from pathlib import Path
from unittest.mock import patch

from companion_robot import voice_loop_demo
from companion_robot.conversation.service import ConversationService
from companion_robot.device.screen_face import ScreenFaceDeviceController
from companion_robot.parent_controls.profiles import ChildProfileRepository
from companion_robot.parent_controls.reading_exercises import ReadingExerciseRepository
from companion_robot.reading.repository import ReadingRepository
from companion_robot.storage.sqlite import connect
from companion_robot.voice.openai_backend import OpenAILanguageModelBackend
from companion_robot.voice_loop_demo import (
    _run_reading_partner,
    _run_reading_partner_v2,
    _select_or_create_profile,
)


async def _text_capture_and_transcribe(stt) -> str:
    """Stands in for voice_loop_demo._capture_and_transcribe() -- no
    recording, no Whisper call. Reads one line of typed text, exactly
    where a real transcript would otherwise have landed."""
    return await asyncio.get_event_loop().run_in_executor(
        None, input, "\nYou (type what the child says): "
    )


async def _text_speak(tts, audio, text: str, speed: float = 1.0) -> None:
    """Stands in for voice_loop_demo._speak() -- no TTS call, no audio
    playback, and deliberately a no-op rather than printing the line
    itself: every real call site already does `print(f"Chitti: ...")`
    right before calling _speak() (so a real voice session's console
    log shows what's being said too), so printing again here would
    just duplicate every line. The one exception --
    _speak_while_thinking()'s escalating "Hmm, let me think..." filler,
    which exists purely to mask real TTS/playback latency -- has
    nothing to mask here and is correctly silent in text mode, not a
    gap."""


async def main() -> None:
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    conn = connect(data_dir / "chitti.db")  # same db the Parent Controls web UI reads from

    llm = OpenAILanguageModelBackend()
    conversation = ConversationService(llm)

    profiles = ChildProfileRepository(conn)
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)

    # Never started -- every set_status_led()/set_reading_text() call
    # _run_reading_partner() makes is a harmless no-op this way, so
    # there's nothing screen-related to fake or keep in sync here.
    # set_reading_spotlight() is the one exception: found live --
    # the hint ladder's own first stage deliberately never says the
    # word out loud ("Let's try that word again..."), relying
    # entirely on the screen highlighting it instead. With no screen
    # at all, that signal just vanished, leaving no way to tell which
    # word was being asked about. Wrapped here (just this one
    # instance, not the class) to print it instead.
    face = ScreenFaceDeviceController()
    _print_spotlight = face.set_reading_spotlight

    def _spotlight_and_print(word: str | None) -> None:
        if word is not None:
            print(f"[Chitti is pointing at: \"{word}\"]")
        _print_spotlight(word)

    face.set_reading_spotlight = _spotlight_and_print

    profile = _select_or_create_profile(profiles)

    is_v2 = os.environ.get("CHITTI_READING_PARTNER_V2") == "1"
    print(f"\n-- Reading Partner {'v2 (decision 0075)' if is_v2 else ''} (text-only test harness) --")
    print("Type what the child would say at each prompt. Ctrl-C to quit.\n")

    reading_partner_fn = _run_reading_partner_v2 if is_v2 else _run_reading_partner
    with (
        patch.object(voice_loop_demo, "_capture_and_transcribe", _text_capture_and_transcribe),
        patch.object(voice_loop_demo, "_speak", _text_speak),
    ):
        next_mode, _switch_trigger_text = await reading_partner_fn(
            conversation,
            tts=None,
            audio=None,
            stt=None,
            reading_repo=reading,
            reading_exercises=reading_exercises,
            face=face,
            child_profile_id=profile.id,
            speed=profile.speech_speed,
            child_age=profile.age,
            child_interest=profile.interest,
            reading_pace_wpm=profile.reading_pace_wpm,
            reading_font_size=profile.reading_font_size,
            reading_font_color=profile.reading_font_color,
        )

    if next_mode is not None:
        print(
            f"\n(Chitti would now switch to mode '{next_mode}' -- this harness "
            "only runs Reading Partner, so stopping here.)"
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nBye!")
