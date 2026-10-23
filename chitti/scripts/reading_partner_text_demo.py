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

Reuses _run_reading_partner() completely unmodified: the call sites
that normally touch real audio (voice_loop_demo._capture_and_transcribe
/ _capture_and_transcribe_after_beep / _speak) are monkeypatched here
to read a line from stdin / print a line to stdout instead, the same
technique this project's own test suite already uses.
_capture_and_transcribe_after_beep() (decision 0084) backs the new
"I'll read it, you repeat after the beep" help step -- text mode just
prints "[BEEP]" instead of playing the real cue tone. Every
other decision this mode has ever shipped (BKT mastery, miscue
alignment, the hint ladder, word-family verification, sentence-by-
sentence resume, etc.) runs exactly as it does on real hardware --
nothing about the reading logic itself is faked, only the two literal
audio I/O points. The screen is skipped the same way
CHITTI_DISABLE_FACE already does on real hardware: a real, unstarted
ScreenFaceDeviceController, whose calls are harmless no-ops when its
render thread was never started -- no separate fake-face class
needed. Two of its methods are wrapped (this one instance, not the
class) to print instead of silently no-op-ing: set_reading_spotlight()
(found live -- the hint ladder's first stage never says the word out
loud, relying on the screen highlight instead) and set_reading_text()
(found live -- the sentence-by-sentence loop shows only the current
sentence on screen, one at a time; without that, a tester typed the
whole passage into one capture instead of reading it one sentence at
a time, since nothing showed which single sentence was expected).

Requires OPENAI_API_KEY in chitti/.env (same as voice_loop_demo.py).

Decision 0075: set CHITTI_READING_PARTNER_V2=1 to exercise the new,
separate model/together/independent/practice flow instead -- same
toggle voice_loop_demo.py's own mode dispatch uses, so this harness
tests whichever version is actually configured.

Decision 0079, found live: a tester read "book generation attempt
failed: ..." (decision 0076's own diagnostic logging, printed with no
context since nothing here configures logging) and reasonably read it
as something being broken -- it is an internal diagnostic the real
session always recovers from automatically (decisions 0077/0078's
fallback chain: LLM story -> hand-written story -> guaranteed word-
drill, never an apology). Annotated below so that's clear in the
moment instead of needing an explanation afterwards.

Usage: python scripts/reading_partner_text_demo.py
"""
import asyncio
import logging
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


class _AnnotatedWarningHandler(logging.Handler):
    """Prefixes voice_loop_demo's own book-generation-attempt-failed
    warning (decision 0076) so it reads as the harmless internal
    diagnostic it is, instead of looking like something broke --
    decision 0079's own "why does generation fail, it shouldn't be
    able to" confusion, found live."""

    def emit(self, record: logging.LogRecord) -> None:
        print(f"[internal, harmless -- falling back automatically] {record.getMessage()}")


async def _text_capture_and_transcribe(stt) -> str:
    """Stands in for voice_loop_demo._capture_and_transcribe() -- no
    recording, no Whisper call. Reads one line of typed text, exactly
    where a real transcript would otherwise have landed."""
    return await asyncio.get_event_loop().run_in_executor(
        None, input, "\nYou (type what the child says): "
    )


async def _text_capture_and_transcribe_after_beep(stt, audio, duration_seconds: float) -> str:
    """Stands in for voice_loop_demo._capture_and_transcribe_after_beep()
    (decision 0084) -- prints the cue tone instead of actually playing
    one, then reads one line of typed text, same as
    _text_capture_and_transcribe() above. `duration_seconds` is real
    hardware's fixed recording window; text mode has nothing to time,
    so it's unused here."""
    print("[BEEP]")
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
    logging.getLogger("companion_robot.voice_loop_demo").addHandler(_AnnotatedWarningHandler())
    logging.getLogger("companion_robot.voice_loop_demo").setLevel(logging.WARNING)

    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    conn = connect(data_dir / "chitti.db")  # same db the Parent Controls web UI reads from

    llm = OpenAILanguageModelBackend()
    conversation = ConversationService(llm)

    profiles = ChildProfileRepository(conn)
    reading = ReadingRepository(conn)
    reading_exercises = ReadingExerciseRepository(conn)

    # Never started -- every set_status_led() call
    # _run_reading_partner() makes is a harmless no-op this way, so
    # there's nothing screen-related to fake or keep in sync here.
    # set_reading_spotlight() and set_reading_text() are the two
    # exceptions, both found live: the hint ladder's own first stage
    # deliberately never says the word out loud ("Let's try that word
    # again..."), relying entirely on the screen highlighting it
    # instead -- and decision 0067's sentence-by-sentence loop shows
    # only the CURRENT sentence on screen, one at a time, never
    # printing which one that is anywhere in text mode. Without
    # either signal, a tester has no way to tell which word is being
    # asked about, or which single sentence (out of the whole passage
    # printed up front) is actually expected right now -- which is
    # exactly how a real session ended up with the whole passage typed
    # into one capture, instead of one sentence at a time. Both
    # wrapped here (just this one instance, not the class) to print
    # instead.
    face = ScreenFaceDeviceController()
    _print_spotlight = face.set_reading_spotlight
    _print_reading_text = face.set_reading_text
    _print_word_grid = face.set_word_grid

    def _spotlight_and_print(word: str | None) -> None:
        if word is not None:
            print(f"[Chitti is pointing at: \"{word}\"]")
        _print_spotlight(word)

    def _reading_text_and_print(lines, **kwargs) -> None:
        if lines is not None:
            shown = " ".join(lines)
            print(f'[Chitti is showing: "{shown}"]')
        _print_reading_text(lines, **kwargs)

    def _word_grid_and_print(words: list[str] | None) -> None:
        if words is not None:
            print(f"[Chitti is showing word blocks: {', '.join(words)}]")
        _print_word_grid(words)

    face.set_reading_spotlight = _spotlight_and_print
    face.set_reading_text = _reading_text_and_print
    face.set_word_grid = _word_grid_and_print

    profile = _select_or_create_profile(profiles)

    is_v2 = os.environ.get("CHITTI_READING_PARTNER_V2") == "1"
    print(f"\n-- Reading Partner {'v2 (decision 0075)' if is_v2 else ''} (text-only test harness) --")
    print("Type what the child would say at each prompt. Ctrl-C to quit.\n")

    reading_partner_fn = _run_reading_partner_v2 if is_v2 else _run_reading_partner
    with (
        patch.object(voice_loop_demo, "_capture_and_transcribe", _text_capture_and_transcribe),
        patch.object(
            voice_loop_demo,
            "_capture_and_transcribe_after_beep",
            _text_capture_and_transcribe_after_beep,
        ),
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
