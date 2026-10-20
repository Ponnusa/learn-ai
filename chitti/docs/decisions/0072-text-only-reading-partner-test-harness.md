# 0072 — Text-only Reading Partner test harness

Date: 2026-10-20
Status: Accepted

## Context

Product owner: *"can u take this reading comprehension testing
without voice text based for now.. later we can merge it there.. i
dont need also screen for now.. lets the whole use case working via
text and then goto screen and voice.. create a new python script to
test using text and llm and parental control and no voice."* Testing
the Reading Partner mode end to end on real hardware means a real mic/
speaker and a real screen in the loop every time, which slows down
iterating on the reading logic itself (hint ladder, mastery, word
family, exercises, follow-ups) -- the actual thing under test -- with
audio/screen concerns that are a separate, later integration step.

## What shipped

New `scripts/reading_partner_text_demo.py`. Reuses
`_run_reading_partner()` completely unmodified -- nothing about the
reading logic is faked. Only the two literal audio I/O call sites,
`voice_loop_demo._capture_and_transcribe()` and `voice_loop_demo._speak()`,
are monkeypatched (same `unittest.mock.patch` technique this project's
own test suite already uses) to a typed-stdin version and a no-op,
respectively:

- `_text_capture_and_transcribe()`: reads one line from stdin instead
  of recording and transcribing audio.
- `_text_speak()`: a no-op. Every real call site already does its own
  `print(f"Chitti: ...")` right before calling `_speak()` (so a real
  voice session's console log shows what's being said too) -- printing
  again here would just duplicate every line. Found while smoke-
  testing: the one exception, `_speak_while_thinking()`'s escalating
  "Hmm, let me think..." filler (exists purely to mask real TTS/
  playback latency), has nothing to mask in text mode and is correctly
  silent now, not a gap.

No screen either, and no new fake class needed for it: a real,
never-`.start()`-ed `ScreenFaceDeviceController` is used as-is --
every `set_status_led()`/`set_reading_text()`/`set_reading_spotlight()`
call it receives is already a harmless no-op when its render thread
was never started, the exact same mechanism `CHITTI_DISABLE_FACE`
(decision 0046) already relies on for the real demo.

Everything else is real: a real `OpenAILanguageModelBackend` (needs
`OPENAI_API_KEY` in `chitti/.env`, same as `voice_loop_demo.py`), and
the real `ReadingRepository`/`ReadingExerciseRepository`/
`ChildProfileRepository` against the same `chitti/data/chitti.db` the
Parent Controls web UI reads from -- a parent's actually-uploaded
exercises and an actual child profile are exercised, not fixtures.
`_select_or_create_profile()` is reused as-is for profile selection
(it was already text-input-based). After `_run_reading_partner()`
returns, if it asked to switch to a different mode, the harness just
reports that and stops -- it only runs Reading Partner, not the full
5-mode dispatch loop.

## Consequences

Verified by hand with a throwaway smoke test (not checked in): a
temp in-memory db, a fake `LanguageModelBackend`, and scripted stdin
answers, confirmed the full exercise-read -> feedback -> comprehension
-> word game -> mode-switch flow runs end to end with clean, non-
duplicated console output and the exercise actually gets marked
consumed in the repository -- the same real code path real hardware
runs, just with text at the two I/O edges.

No new automated test was added for this script itself (it's a manual
test harness, not production code with its own behavior to regression-
test) -- its entire value is that it delegates to already-tested
production code. Full suite unaffected: 529 passed, 2 pre-existing,
unrelated `test_screen_face_rendering.py` failures (no usable SDL
video driver in this dev environment).

## Not yet done

- Only Reading Partner is wired up -- the other four modes
  (Teachable-Friend, Story Companion, Just Chat, Lullaby) don't have a
  text harness yet; scoped to what was actually asked.
- No shell wrapper (`scripts/run_*.sh` exists for other entry points)
  -- `python scripts/reading_partner_text_demo.py` is simple enough
  on its own; can be added later if it becomes a frequently-run tool.
- This is explicitly a stepping stone, per the product owner's own
  framing ("later we can merge it there... then go to screen and
  voice") -- the real audio/screen integration is unchanged and still
  the eventual target, not replaced by this.
