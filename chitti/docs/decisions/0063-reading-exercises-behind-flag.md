# 0063 — Parent-uploaded reading exercises gated behind a flag

Date: 2026-10-19
Status: Accepted

## Context

Product owner wants to favor the LLM-generated book path over
parent-uploaded exercises (decision 0052) for now -- the LLM path
already adapts content to the child's age (`age=child_age or 6` in
the existing `generate_decodable_book()` call), and the product
direction is to keep developing that path rather than the fixed-text
upload path, without discarding the upload feature outright.

## What shipped

`_run_reading_partner()`'s check for a pending parent-uploaded
exercise is now gated behind `CHITTI_ENABLE_READING_EXERCISES=1`
(default off, same env-var-flag precedent as decision 0046's
`CHITTI_DISABLE_FACE`): with the flag unset, `exercise` is always
`None` regardless of what's pending, and the loop falls through to
the LLM-generated book path exactly as if nothing had been uploaded.
Nothing about the upload feature itself changed -- the Parent
Controls UI, `ReadingExerciseRepository`, and the exercise-consumption
logic are all untouched and fully intact, just not consulted while
the flag is off. Flipping it back on later needs no code changes.

## Consequences

Most existing Reading Partner tests in `test_voice_loop_demo_intent.py`
use a pending exercise purely as a convenient, deterministic content
fixture (not to test the exercise feature itself) -- a new
module-level `autouse=True` pytest fixture sets the flag on for every
test in that file by default, preserving all of their existing
behavior with no per-test changes. One new, explicit test
(`test_run_reading_partner_exercise_is_ignored_when_flag_is_off`)
overrides that fixture with `monkeypatch.delenv()` to confirm the real
default (flag unset): a pending exercise is never read and never
marked consumed, and the book comes from the LLM instead. Full suite:
472 passed, 1 skipped (pygame unavailable in this dev environment,
pre-existing).

## Not yet done

- Story continuity across sessions (the LLM picking up a narrative
  thread from a previous book rather than each one being a self-
  contained story) -- not implemented; the LLM path's `age` adaptation
  it already had is what's being favored here, not a new continuity
  feature.
- Re-enabling parent-uploaded exercises by default -- open until the
  product direction is revisited.
