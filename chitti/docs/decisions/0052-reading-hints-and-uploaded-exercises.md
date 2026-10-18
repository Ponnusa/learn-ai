# 0052 — Reading Partner graduated hints + parent-uploaded exercises

Date: 2026-10-18
Status: Accepted

## Context

Product owner shared a proposed robot-integration architecture for
phono-storyforge (parent interface / reading engine / robot controller
split) and asked for a feasibility check against what Chitti actually
has. Verdict: the split already exists here -- decision 0051 ported
the algorithms into `reading/` and Chitti already has its own robot
controller (`device/`, `audio/`), so most of that proposal confirmed
architecture already built, not new work. Two concrete gaps came out
of that review as worth prioritizing:

1. **Graduated hint + retry** when a child struggles on a word --
   `_run_reading_partner()` was one-shot: capture the whole read, grade
   it *after the fact*, with no in-session help at all.
2. **Parent-uploaded reading exercises**, kept separate from LLM-
   generated books -- there was no way to assign a specific passage
   (school homework), every book was generated.

**Feasibility finding that reshaped feature 1**: the source proposal's
"robot listens live, notices a pause, jumps in with a hint mid-
sentence" isn't buildable on Chitti's current audio I/O.
`_capture_and_transcribe()` is push-to-talk -- record until Enter is
pressed, *then* transcribe once. There's no streaming/partial
transcription or voice-activity detection, so there's no way to notice
a child pausing mid-read. The feasible shape is **post-hoc**: let the
child finish the whole passage (as before), grade it, and if grading
surfaced a real miss, run a short hint-and-retry exchange for that one
word before the normal feedback -- not a live interruption. Scoped to
one hint-word per book.

## What shipped

**Graduated hint + retry** (`reading/hints.py`, new): `pick_hint_word()`
scans `AssessmentResult.miscues` (already produced by `assess()`) for
the first `SUBSTITUTION`/`OMISSION` -- a real error, as `assess()`
itself already defines it; `self_correction`/`hesitation`/`insertion`
miscues are skipped. `build_hint_line(word, stage)` returns the
three-stage ladder: stage 0 encourages and asks the child to sound it
out; stage 1 gives the first sound, read straight from
`decodability.decompose(word).graphemes[0]` (no new phonics logic);
stage 2 says the word and invites one more try. `_run_reading_partner()`
runs this as a loop of up to 3 rounds right after `assess()` and before
`update_from_evidence()` -- each round speaks the hint, captures a
reply with the existing `_capture_and_transcribe()`, and compares it
with `clean_word()`. A correct retry breaks the loop with a short
"There you go!"; three misses still fall through to ordinary feedback
with no penalty. Every round's evidence (`attribute_evidence(align(word,
attempt))`) is merged into `assessment.grapheme_evidence` before the
single existing `update_from_evidence()` call, so a corrected retry
becomes a real extra BKT opportunity rather than being thrown away.

**Parent-uploaded reading exercises**: new `reading_exercises` table
(`storage/migrations.py`) and `ReadingExerciseRepository`
(`parent_controls/reading_exercises.py`), scoped per child -- a
specific assignment, not a shared library like `stories`. New Parent
Controls routes/template (`/profiles/<id>/reading-exercises`), one
more action link on the profiles page. `_run_reading_partner()` checks
`next_pending_for_child()` at the top of every loop iteration; if one
exists, it's wrapped directly into the same `GeneratedBook` dataclass
the LLM path returns (`generation_source="parent_uploaded"`) -- no
decodability check, no LLM call at all, and every downstream line
(screen display, `assess()`, the hint logic above) needed zero changes
because the shape is identical. Marked consumed the moment it's picked
up, so it's read once, not every session, then Reading Partner falls
back to generating its own books.

**Deliberately no `check_speech()` screening on exercise content** --
same trust model risk register #14 already establishes for parent-
uploaded stories and lullaby audio: the parent is the authorizing
adult for their own child. A conscious choice, not an oversight (see
new risk register row #27).

## Consequences

19 new tests: `test_reading_hints.py` (8), `test_reading_exercises_repository.py`
(6), additions to `test_parent_controls_app.py` (5, the new routes),
and 3 new end-to-end tests in `test_voice_loop_demo_intent.py` driving
`_run_reading_partner()` with fakes -- a pending exercise used
verbatim with the LLM never called, a hint retry that succeeds and
feeds two real BKT opportunities (one wrong, one right) for the same
grapheme, and three failed retries still reaching ordinary feedback
with no penalty and no hang. Two pre-existing `_run_reading_partner`
tests needed updating for the new `reading_exercises` parameter; one
of them (the "never checks the read-aloud for a switch" test) also
needed its mocked capture turned from a static list into a side-effect
function, since its read-aloud text ("tell me a story") is unrelated
to the generated book and reliably triggers the new hint loop, whose
exact number of extra captures isn't worth predicting by hand. Full
suite: 403 passed, 1 skipped (pre-existing, decision 0040).

## Not yet done

- Live, mid-sentence stuck-detection -- needs streaming STT + voice-
  activity detection, which Chitti doesn't have at all today; a much
  bigger, separate lift than this decision's post-hoc shape.
- Hinting on more than one missed word per book.
- OCR/photo/PDF exercise upload -- pasted/typed text only.
- Comprehension questions and a parent progress report -- still
  separate, larger follow-ups, not bundled into this decision.
- Wi-Fi-drop resilience during a reading session -- a real, confirmed
  cross-cutting gap (every mode, not just this one), tracked but not
  fixed here.
