# 0060 — Reading feedback surfaces every missed word, not just the hinted one

Date: 2026-10-19
Status: Accepted

## Context

A real Pi session (pasted log) read roughly: the child read "The
Bunny and the Apple" haltingly, omitting "little" (hinted, eventually
resolved -- the child said it correctly after the ladder) and
separately misreading "garden" as "Gotten" (never addressed at all).
The final feedback was: *"Good try! Reading can be tricky sometimes.
I especially loved how you read 'bunny'!"* -- no mention of "garden"
anywhere, despite it being a real, substantial miscue. Explicit
product feedback: *"after reading the text it should show the result
and how did the child fare in a nice way. Also give some words for
him to practice."*

Root cause: the hint-and-retry loop (decision 0052) is deliberately
scoped to one word per book (its own V1 limit), and
`build_reading_feedback()` only ever knew about *that* word --
`hint_word`, passed only when unresolved. Every other real miss in
the same read was invisible to feedback, which either repeated the
one hinted word or fell back to praising an unrelated correctly-read
word. The session above is exactly this gap: two real misses, only
one nameable anywhere.

## What shipped

**`reading/hints.py`**: extracted `pick_hint_word()`'s filtering logic
(not trivially short, not a sight word) into a new public
`is_worth_practicing(word)`, so `feedback.py` can apply the exact same
bar instead of a second, potentially-drifting definition.

**`reading/feedback.py`**: `build_reading_feedback()`'s signature
changed from `hint_word: str | None` to `resolved_word: str | None` --
the word to *exclude* (because the hint ladder already fixed it live
and re-mentioning it would be redundant), not a word to specially
mention. A new `_practice_words()` walks every miscue in
`assessment.miscues` (not just one), filters through
`is_worth_practicing()`, dedupes, and caps at 3 -- so "garden" now
surfaces exactly when "little" doesn't need to. If there's nothing to
practice (a clean read), the existing decision-0055 standout-word
praise still applies -- a clean read still gets something specific
to the read, not just "well done."

**`voice_loop_demo.py`**'s call site: `resolved_word=hint_word if
hint_resolved else None` -- the only change needed, since
`build_reading_feedback()` now derives everything else itself from
`assessment`.

## Consequences

`test_reading_feedback.py`'s two `hint_word`-based tests (which relied
on a perfect read plus a manually-forced hint word -- a premise that
no longer exists once practice words come from real miscues) were
replaced with tests against an actual two-miscue read: both words
surface with no resolution; the resolved one is excluded while the
other still surfaces; a 6-miscue read caps at exactly 3. `test_reading_hints.py`
unaffected (`pick_hint_word()`'s own behavior is unchanged, just
refactored to share its filter). Full suite: 461 passed, 1 skipped
(pygame unavailable in this dev environment, pre-existing).

## Not yet done

- The broader "feels like a sequence of disconnected steps" feedback
  (hint ladder -> feedback -> comprehension Q&A -> word game -> "want
  another one," each its own `Chitti: ...` line) wasn't addressed here
  -- this decision is scoped to feedback content specifically. Pacing/
  narration across the whole post-read sequence is a separate,
  larger, more subjective pass if the product owner wants it pursued.
