# 0065 — Every real miss gets the hint ladder; a modeled answer isn't mastery evidence

Date: 2026-10-20
Status: Accepted

## Context

Two related gaps identified from the same product-owner critique that
produced the 0064-0067 roadmap, both touching `_run_reading_partner()`'s
hint loop in `voice_loop_demo.py`:

**Gap A**: the hint-and-retry loop ran once, for `pick_hint_word()`'s
*first* result only -- a deliberate V1 limit from decision 0052.
`feedback.py`'s `_practice_words()` (decision 0060) already lists
every real miss in the spoken *summary*, but only one of them ever
got the interactive encourage -> hint -> retry treatment live. A read
with two real misses only ever worked through one of them.

**Gap B**: every hint stage's retry evidence -- including the final
stage, where Chitti has already said the word outright -- fed
`assessment.grapheme_evidence` identically to an independent correct
read. A child who just echoes back a word Chitti told them was
counted by `update_from_evidence()` as if they'd decoded it
themselves. The *earlier* stages (sounded out after a sound/blend
cue) are real decoding work and should still count; only "told the
answer, then repeated it" is an echo, not evidence.

## What shipped

**`reading/hints.py`**: `pick_hint_word()` generalized into
`pick_hint_words(assessment, max_words=3)` -- every real-error word
(substitution/omission, `is_worth_practicing()`), deduped, in reading
order, capped at `_MAX_HINT_WORDS = 3` (matches `feedback.py`'s own
`_MAX_PRACTICE_WORDS`, so the spoken summary and what was actually
hinted on live agree on the same cap). `pick_hint_word()` kept as a
single-result convenience wrapper (`pick_hint_words(..., max_words=1)[0]`)
for existing callers/tests.

**`voice_loop_demo.py`**: the hint section now loops over
`pick_hint_words(assessment)` instead of a single word, reusing the
existing per-word stage loop unchanged, just wrapped one level up.
`resolved_words: list[str]` accumulates every word resolved before
exhausting its ladder, replacing the old single `resolved_word`.
Gap B's fix: retry evidence is only fed into
`assessment.grapheme_evidence` when `stage < HINT_STAGES - 1` -- the
final stage's attempt (after Chitti has said the word outright) is
never attributed. `face.set_reading_spotlight(None)` is only called
once, after the whole multi-word loop, and only if there was at least
one hint word (so a clean read with zero misses doesn't pick up an
extra spotlight-clear call).

**`reading/feedback.py`**: `build_reading_feedback()`'s
`resolved_word: str | None` became `resolved_words: list[str] | None`
so multiple resolved words are all excluded from the practice-words
summary, not just one.

## Consequences

`test_reading_hints.py`: new `pick_hint_words()` section -- returns
every real miss in order, caps at `max_words`, dedupes, empty list on
a clean read; `pick_hint_word()` reconfirmed as the first of
`pick_hint_words()`.

`test_reading_feedback.py`: `test_feedback_excludes_the_resolved_hint_word_but_keeps_other_misses`
updated for the list signature; added
`test_feedback_excludes_multiple_resolved_words_at_once` (two resolved
words, both excluded, verified against real miscues from `assess()`).

`test_voice_loop_demo_intent.py`: renamed and extended
`..._continues_without_penalty_after_three_misses` to
`..._after_four_misses` (ladder is now 4 stages, decision 0064).
Added `test_run_reading_partner_hints_every_real_miss_not_just_the_first`
(Gap A: two misses, one resolved early, one never resolved -- both
get the ladder, feedback excludes only the resolved one). Added
`test_run_reading_partner_final_stage_resolution_does_not_feed_mastery`
(Gap B: a word only resolved via the final "say it back" stage ends
with exactly 4 opportunities recorded for its first grapheme -- the
original miscue plus the three *earlier* stages' real attempts -- not
5, which would mean the told-the-answer attempt was wrongly counted
as a fifth independent opportunity).

Full suite: 486 passed (2 pre-existing, unrelated `test_screen_face_rendering.py`
failures -- no usable SDL video driver in this dev environment, not
touched by this change).

## Not yet done

- Word-family generalization check (decision 0066) and sentence-by-
  sentence reading with persistent position (decision 0067) --
  separate decisions in the same approved roadmap, not started yet.
