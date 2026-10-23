# 0084 — Word-family grid (one take, not one at a time) + a beep-cued "repeat after me" help step

Date: 2026-10-23
Status: Accepted

## Context

Direct product-owner feedback after trying the Reading Partner for
real: *"its too detail.. i mean its very slow... when we have similar
words, all similar words can be shown together on the screen, each
one nicely placed in a nice rectangle block... so we dont need too
many rounds."* And separately: *"if a child doesn't read correctly...
i will read the sentence and then u repeat after me... give a heads
up like 'now its ur turn' and then put a beep... so child knows when
to react rather than i press enter."*

Two real, separate asks, each narrowed down before building (asked
via clarifying questions rather than assumed):
1. Word-family practice (decision 0066) asked one candidate word at a
   time -- its own spotlight, its own capture, its own reaction --
   turning a small reading task into several round trips.
2. The per-sentence reread after a hint ladder (decisions 0074/0081)
   asked for a blind independent reread, captured via "press Enter to
   start talking" -- real hardware has no voice-activity detection to
   replace that with (`audio/real.py`'s own note: no ARMv6 wheel for
   the wake-word library), so a keypress was the only option so far.
   Confirmed scope with the product owner: one take covering every
   word-family candidate (not per-word asking); the capture window
   sized to the sentence/age-based pace already driving the
   teleprompter; and the beep cue built for just this one new help
   step first, not rolled out to every capture in the file yet.

## What shipped

**`device/screen_face.py`**: new `set_word_grid(words)` /
`_draw_word_grid()` -- every candidate shown at once, each in its own
rounded rectangle block (1 column for 1-2 words, 2 columns for 3+,
same "simple and good enough" bar as the existing `_wrap_text()`).
Independent state alongside the existing spotlight/reading-text/face,
same pattern `set_reading_spotlight()` already established.

**`reading/word_game.py`**: untouched -- `is_correct_answer()` was
already lenient enough (checks if the target word appears anywhere in
the reply) to reuse directly against one shared transcript instead of
one per word.

**`voice_loop_demo.py`**, `_run_word_family_practice()`: the offer
(yes/no) is unchanged; accepting now shows the whole set via
`set_word_grid()`, asks "Can you read all of these words for me?"
once, captures once, then reacts to each word in turn against that
one transcript -- one capture instead of N.

**`audio/tones.py`** (new module): `generate_beep()` -- a short,
deterministic synthesized tone (880Hz, 250ms, faded in/out to avoid a
click), raw PCM matching `audio/real.py`'s exact playback contract
(16-bit signed LE mono at `PLAYBACK_SAMPLE_RATE`) so it plays through
the same `audio.play()` every spoken reply already uses. No TTS call,
no audio asset to ship.

**`voice_loop_demo.py`**, new capture path: `_record_clip_for_duration()`
(arecord's own `-d` flag, no keypress) and
`_capture_and_transcribe_after_beep(stt, audio, duration_seconds)`
(plays the beep, then records for a fixed window -- "listen for about
this long," not "listen until you stop talking," since there's no
VAD to do the latter). `_sentence_capture_seconds(sentence,
reading_pace_wpm)` sizes that window from word count at the same
age-based pace already driving the teleprompter (`reading_pace_wpm`),
plus a flat buffer for reacting to the beep, floored at
`_MIN_CAPTURE_SECONDS` so a one-word sentence still gets a fair
window.

**`_run_reading_partner()`'s reread step** (decisions 0074/0081) now:
models the sentence itself first, at `speed * 0.75`
(`_MODEL_READ_SPEED_MULTIPLIER`) -- "I'll read it for you first.
Listen:" -- then "Now it's your turn! Say it after the beep.", then
captures via the new beep-cued, duration-sized path instead of
`_capture_and_transcribe()`. Everything downstream (decision 0081's
re-assessment against the sentence, the one-shot correction cycle for
a new miscue) is unchanged -- only how the attempt gets captured
changed, not how it's graded or reacted to.

Scoped deliberately to just this one step, not rolled out to every
capture in the file (the product owner's own call, to see how it
feels on real hardware first) -- v2's analogous final-reread step,
the main read-aloud, the hint ladder's own retries, and the word game
all still use the original keypress-based `_capture_and_transcribe()`.

**`scripts/reading_partner_text_demo.py`**: a third monkeypatch
(`_capture_and_transcribe_after_beep` -> prints `[BEEP]` instead of
playing one) and a `set_word_grid` print wrap, matching the existing
spotlight/reading-text visibility pattern -- otherwise this new flow
would be invisible in the text-only harness.

## Consequences

New tests: `test_audio_tones.py` (beep format/determinism/no-clipping/
fade-in); `_sentence_capture_seconds()`'s scaling, floor, and
non-positive-pace fallback (`test_voice_loop_demo_intent.py`). Every
existing test that exercised the per-sentence reread needed its
`_capture_and_transcribe` patch extended to also cover
`_capture_and_transcribe_after_beep` -- added a small
`_patch_captures()` test helper (both names patched to one shared
mock, since a list-based `side_effect` ignores call arguments
entirely) rather than hand-editing each one differently. Word-family
tests updated for the one-capture flow and the new `face.word_grids`
assertions.

Full suite: 614 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

The beep-cued capture is live for exactly one step. Whether it feels
right on real hardware (reaction time, whether the fixed window is
long/short enough, whether the beep itself is a good cue sound) is
still to be tried -- rolling it out to every other capture in the
file is a separate decision, deliberately not made here. The
word-grid's layout is untested on an actual physical screen yet
either (no SDL driver works in this dev environment at all); it's
only verified through `voice_loop_demo.py`'s own orchestration tests
(`face.word_grids`), not a real render.
