# 0069 — Parent-uploaded exercises default back to enabled

Date: 2026-10-20
Status: Accepted (supersedes 0063's default)

## Context

Live bug report: *"though we have reading materials from parent, i
get this error: Chitti: I'm having trouble coming up with a story
right now... but based on previous shouldn't it get something from
llm based on previous history with child, that way it will be
seamless."* Investigated and confirmed: `CHITTI_ENABLE_READING_EXERCISES`
has defaulted to **off** since decision 0063 ("favor the LLM path for
now"), and nothing in any real run configuration (`.env`, systemd
unit, launch script) ever sets it. So a real parent-uploaded exercise
was sitting in the database the whole time, completely unconsulted --
`_run_reading_partner()` went straight to `generate_decodable_book()`,
which then hit `BookGenerationError` (the LLM failed to produce a
safe, fully decodable draft within its retry budget) and the child was
left with only the flat apology line, despite real material being
available the entire time.

Decisions 0066-0068 have since built real, useful depth onto the
exercises path specifically (word-family practice, sentence-by-
sentence resume, re-read offers, themed follow-ups) -- all of it was
silently inert in practice because the path itself was off by
default. Asked directly: should parent-uploaded material go back to
being the primary path? Confirmed: yes, flip the default back on.

## What shipped

**`voice_loop_demo.py`**: `exercises_enabled` changed from
`os.environ.get("CHITTI_ENABLE_READING_EXERCISES") == "1"` (opt-in,
default off) to `os.environ.get("CHITTI_ENABLE_READING_EXERCISES", "1") != "0"`
(opt-OUT, default on) -- a pending parent exercise is now the primary
path again whenever one exists, with every decision built on top of
it (0052, 0066, 0067, 0068) active by default. `CHITTI_ENABLE_READING_EXERCISES=0`
is the new way to fall back to the LLM-only behavior 0063 had made the
default; anyone who had explicitly set `=1` is unaffected (still on).

This directly fixes the reported dead-end: with exercises enabled by
default, a pending one is read instead of ever reaching
`generate_decodable_book()` in the first place for that turn.

## Consequences

Renamed/rewrote `test_run_reading_partner_exercise_is_ignored_when_flag_is_off`
(whose entire premise -- "unset means ignored" -- is now backwards) into
`test_run_reading_partner_uses_a_pending_exercise_with_the_flag_unset`,
asserting the new default: an unset flag still reads and consumes a
pending exercise, never reaching the LLM at all. Added a new
`test_run_reading_partner_exercise_is_ignored_when_flag_explicitly_off`
confirming `=0` is still a real, working opt-out (never read, never
consumed, LLM path used instead) -- the behavior the old default-off
test used to check, now reached by an explicit setting instead of the
default. The autouse `_reading_exercises_enabled` fixture's
`setenv("1")` is now redundant against the real default but kept, so
every other test in the file stays correct even if the default changes
again later.

Full suite: 526 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- The underlying `BookGenerationError` dead-end itself (the LLM path
  failing with nothing but an apology) is still exactly as before --
  this decision fixes the specific reported case (exercises silently
  unused) by making sure the exercise path is actually reached, not by
  changing what happens when LLM generation itself fails with no
  exercise available at all. Asked explicitly and declined for now: a
  safety-net fallback from a failed LLM generation to a parent exercise
  (pending or previously-read) regardless of this flag -- worth
  revisiting if `BookGenerationError` is ever hit again with no
  exercise in play.
- No change to why `generate_decodable_book()` failed in the reported
  session in the first place (LLM reliability, model choice, or prompt
  budget) -- not diagnosable from this session without the actual
  failing prompt/reply, and moot for the reported case specifically
  since the exercise is now used instead.
