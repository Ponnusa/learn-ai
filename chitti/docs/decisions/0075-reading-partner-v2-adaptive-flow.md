# 0075 — Reading Partner v2: a second, switchable adaptive flow

Date: 2026-10-20
Status: Accepted

## Context

Product owner, after a detailed critique of the original Reading
Partner flow (decisions 0051-0074): *"this is how i want the reading
companion to work.. but let's not affect the other one.. create a new
version for this and take it from here. so at any point we can get
back to the old.. as we have built a lots of parts."*

The critique proposed a materially different flow from the original's
own (read the whole passage once → graduated hint-and-retry ladder
for missed words → feedback → comprehension): invite an independent
try first; only if it's not clean, model the sentence, read it
together (supported, not assessed), then let the child try
independently again; practice only the words that still turn out hard
(capped at two); reread once; then check understanding -- and
explicitly asked for this as a **deterministic state machine**, not
an LLM deciding what happens next, with the LLM only ever phrasing
questions/reactions. The explicit instruction was to build this as a
new, separate, switchable version, not to modify the original.

## What shipped

**New module `reading/session_state.py`** -- pure, I/O-free, never
imported by the original `_run_reading_partner()`:
- `ReadingState` enum: `INTRO, INDEPENDENT_READ, MODEL_READ,
  READ_TOGETHER, SECOND_INDEPENDENT_READ, WORD_PRACTICE,
  FINAL_REREAD, COMPREHENSION, COMPLETE` -- the exact states the
  critique itself named.
- `SentenceSession`: owns one sentence's target text, current state,
  every graded attempt, and the practice-word list. `decide_after_first_read()`
  skips straight to `COMPREHENSION` on a clean read (accuracy >= 0.95,
  the same banding `feedback.py` already uses for its own "really
  well" praise) or moves to `MODEL_READ` otherwise.
  `decide_after_second_read()` picks up to `MAX_PRACTICE_WORDS` (2)
  real misses via `hints.pick_hint_words()` -- reusing the original's
  own proven, deterministic miscue-detection core rather than a second
  grading algorithm, just driving a different flow around it.
- `seems_like_a_help_request()` / `seems_like_a_stop_request()`:
  fixed-phrase, deterministic checks (an empty/near-empty capture or
  an explicit ask counts as wanting help, not a bad reading attempt;
  explicit phrases like "I'm done"/"this is too hard" end the session
  warmly instead of pushing through a frustrated child) -- per the
  critique's own "the LLM must not silently switch the target or
  declare an answer correct without evidence," decisions here are
  fixed-list, not an LLM's judgment call.

**New `voice_loop_demo._run_reading_partner_v2()`** -- a second,
complete orchestration function, physically separate from (and never
calling into) the original `_run_reading_partner()`. Drives
`SentenceSession` through every sentence of a book/exercise: invite →
grade the first attempt (or recognize a help request) → model → read
together (captured but never graded or fed to mastery -- "doesn't
prove independent reading") → second independent attempt (graded,
feeds mastery) → word practice for up to 2 still-hard words (each:
Chitti models the word, the child echoes it -- not graded, same echo-
isn't-evidence principle as decision 0065 -- then tries it once more
fully independently, which IS graded) → one final whole-sentence
reread (not graded, same fluency-only reasoning as decision 0074) →
one comprehension question anchored to that sentence (reusing
`generate_comprehension_questions()`/`_ask_and_react_to_question()`
as-is -- both are general-purpose, not v1-specific).

**Gated behind `CHITTI_READING_PARTNER_V2=1`** (default off) in
`run_mode_dispatch_loop()`'s mode-"5" branch: a one-line
`reading_partner_fn = _run_reading_partner_v2 if ... else _run_reading_partner`
pick, with zero changes to the original function or its call site's
own arguments. Flipping the flag off (or leaving it unset) is the
"get back to the old at any point" the instruction asked for.

**`scripts/reading_partner_text_demo.py`** (decision 0072) also
respects the same flag, so the new flow is immediately testable via
text without touching voice/screen hardware, same as the original.

Deliberately narrower than the original for this first version: no
word game (decision 0057), no word-family generalization check
(decision 0066), no re-read-the-same-exercise offer or themed follow-
up (decision 0068) -- none of those are part of the critique's own
described flow; "take it from here" was the instruction, not "port
everything first." Book/exercise selection (decision 0052/0063/0069)
is duplicated, not shared, so neither version needs to change if the
other's selection logic ever does. Mastery (`reading/mastery.py`'s
BKT evidence) updates the same `ReadingProfile` the original uses --
a child's phonics mastery is the same fact regardless of which flow
taught it -- but decision 0067's cross-session passage-position
resume (`current_passage_key`/`current_sentence_index`) is
deliberately NOT used by v2, to avoid the two very differently-shaped
flows colliding over the same two profile fields.

Two honest, unavoidable approximations, both already true throughout
the original mode for the same hardware reasons: "read together" is
sequential (Chitti models, then the child reads), not literally
simultaneous -- `_capture_and_transcribe()` is push-to-talk with one
microphone, no live full-duplex audio to read alongside. And the
teleprompter highlight during modeling reuses decision 0053's existing
wpm-paced autoscroll, not live TTS-word-timing-synced highlighting --
this backend's TTS call returns finished audio, not word-level
timestamps, to sync against.

## Consequences

New `test_reading_session_state.py` (15 tests): every state
transition, the clean-read skip, the practice-word cap, and both
fixed-phrase checks, all pure and fake-free.

New `test_voice_loop_demo_reading_partner_v2.py` (7 tests), deliberately
separate from `test_voice_loop_demo_intent.py` (which covers the
original, untouched): a clean first read skips straight to
comprehension; a rough read goes through model → together → second
attempt and skips practice once the second attempt is clean; a still-
difficult word triggers word practice, spotlighting, and the final
reread; an empty/explicit help-request capture is never graded as a
bad read; an explicit stop request ends the session warmly without
ever reaching comprehension; a comprehension question is asked and
reacted to; and v1/v2 share the same `ReadingProfile` mastery state.

Full `test_voice_loop_demo_intent.py` suite (v1's own tests) passes
completely unchanged -- confirmed by running the whole suite after
every step of this decision, not just once at the end.

Full suite: 560 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- STT-confidence-based "treat an uncertain transcript as evidence with
  a confidence level, not unquestionable truth" (the critique's own
  technical-detail callout) -- not addressed; the
  `SpeechRecognitionBackend.transcribe()` interface returns plain text
  with no confidence signal at all today. Every transcript is taken at
  face value, same as the original mode and everywhere else in this
  codebase.
- No word game, word-family check, re-read offer, or themed follow-up
  in v2 yet -- intentionally not ported in this first version.
- No cross-session passage-position resume for v2 (decision 0067's
  own feature, deliberately not reused here -- see above).
- The "read together" and modeling-highlight approximations above are
  the best available given this hardware/backend combination, not a
  temporary gap expected to close soon.
