# 0026 — Posed-challenge extraction fix + child-as-teacher rhythm

Date: 2026-10-16
Status: Accepted

## Context

Two independent review passes on a real Teachable-Friend transcript
surfaced issues in decision 0025's posed-challenge tracking and in
how Chitti behaves once the child starts teaching it something.

## Part 1: two confirmed bugs in posed-challenge extraction

Found by actually running `_resolve_math_check()`/`extract_posed_
challenge()` against the real transcript, not by inspection.

**Bug 1 — stale operand capture.** `extract_posed_challenge()`
searched the whole reply and took the first number-pair-near-"more"
match. A reply that recaps an already-resolved problem before (or
without) posing a new one got its old numbers misread as a fresh
challenge: *"...add one for the first car and one more for the
second car, you get to five!"* (pure recap) was read as a new
challenge `(3, 1)`. The next child turn got checked against that
stale pair, producing a nonsense verified note: *"3+1=2, incorrect,
should be 4"* -- about a question never asked.

**Bug 2 — a question misread as an answer.** The bare-number check
couldn't distinguish "the child is answering" from "the child is
asking something back." *"If we start at five and count two more
numbers, what comes next?"* -- not an answer, a rephrased question --
had its trailing "two" read as a claimed sum, again producing a
nonsense "incorrect" verdict.

Both relocated the exact risk this feature exists to eliminate (an
unverified fact silently steering the model) into the checker itself
-- arguably worse, since it carries a "VERIFIED" label.

### Fix

- `extract_posed_challenge()` now searches only the reply's *last
  sentence ending in "?"*, plus the sentence immediately before it
  for context, instead of the whole reply (`_last_question_window()`
  in `education/math_check.py`). Falls back to whole-text search when
  no sentence ends in "?" at all, preserving every previously-correct
  case with no question in it (e.g. "2 treats plus 3 berries
  makes...").
- `_resolve_math_check()` (`voice_loop_demo.py`) now skips the
  bare-number-vs-pending-challenge check entirely when the child's
  own reply ends in "?" -- a self-stated equation still counts even
  inside a question ("is 2 plus 2 four?"), only the pending-challenge
  path is skipped.

Both fixes were verified by replaying the real transcript through the
actual functions before and after -- both bugs resolved, zero
regressions on every previously-correct turn in that same transcript.

## Part 2: child-as-teacher rhythm

A second review of the same transcript's role-play portion found a
consistent pattern: once the child starts teaching Chitti a method,
Chitti kept re-taking control by asking its own new guiding question
each turn, instead of attempting the step itself and asking the child
to confirm or correct it. Real examples: *"What's the first number
after five?"* and *"what comes after six?"* (guiding questions) where
*"I think it's seven -- am I right, teacher?"* (attempt-and-confirm)
would have kept the child in the verifying role. Also: confirming only
the final number and changing topic immediately, rather than
restating the full method before moving on.

### Fix

Added to `TEACHABLE_FRIEND_SYSTEM_PROMPT`: once the child is actually
teaching Chitti something, stay a genuine learner for the rest of
that exchange -- attempt the next step and ask for confirmation rather
than asking a new guiding question, say the whole method back (not
just the final number) before moving on, and phrase any invitation to
try the method on a new example as something to do together rather
than an abstract "how would you explain this to someone else."

Prompt wording only, same honesty-about-limits as everything else
here -- not mechanically enforceable.

## Consequences

8 new/updated unit tests (154 total passing): both bug-fix regression
cases replayed from the real transcript, plus the question-vs-answer
distinction.

## Not yet done

Once Chitti starts stating its own attempted answers (a direct
consequence of the rhythm fix), those attempts are unverified by
`math_check` -- only the child's claims are checked. That's likely
fine (the design intent is the child catches Chitti's mistakes,
including a deliberate safe one per the original Teachable-Friend
spec), but it's a real asymmetry, noted here rather than silently
assumed away.
