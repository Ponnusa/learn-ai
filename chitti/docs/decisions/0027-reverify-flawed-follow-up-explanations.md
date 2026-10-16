# 0027 — Re-verify a flawed follow-up explanation instead of letting it expire

Date: 2026-10-16
Status: Accepted

## Context

A real transcript surfaced the most concerning failure mode found so
far. Chitti correctly attempted "4 plus 2 equals 6" (right) and asked
the child to confirm. The child wrongly insisted "It is 7." Our
checker *did* fire correctly here (verified: 4+2≠7, correct is 6),
which is why Chitti's next reply asked the child to walk through
their counting instead of just agreeing -- the ask-first behavior
from decision 0025 working as designed.

But the child's explanation was itself a miscount ("four five six
seven" -- three steps from four, not two), and on that follow-up
turn `pending_challenge` had already been cleared, so nothing
re-checked it. Chitti evaluated the flawed explanation entirely on
its own judgment and capitulated: *"So 4 plus 2 is definitely 7."*
A verified-correct position got talked out of existence by a
confident but wrong explanation, with nothing catching it. This is a
materially worse failure than "unverified arithmetic might be wrong"
-- it's "a verified-correct fact can be overridden by social
pressure," the exact thing a correctness layer exists to prevent.

## Fix

`voice_loop_demo.py` no longer clears `pending_challenge` after an
incorrect result -- it re-arms it with the *same* `(a, b)` pair, and
skips `extract_posed_challenge()` that turn so Chitti's "explain more"
reply can't overwrite it with something else it happens to mention.
The next child turn -- whether it's an explanation, a retry, or
anything else with a number in it -- gets checked against the same
problem again, not left to the model's own judgment.

A new `incorrect_streak` counter tracks consecutive incorrect results
for the same problem. `build_math_check_note()` gained an
`already_tried` parameter: on a first incorrect result it behaves as
before (ask them to explain, offer a hint); on a second or later
consecutive incorrect result for the same problem, the note
explicitly says their explanation doesn't add up and tells the model
to stop asking and show the concrete walkthrough now -- preventing
an indefinite "ask again" loop and, per this transcript, preventing
exactly the capitulation that happened.

The state-transition logic was extracted into a small pure function,
`_update_challenge_state(math_check, incorrect_streak)`, so it's
directly unit-testable without needing the full audio/LLM loop.

## Consequences

8 new/updated unit tests (158 total passing), including the real
4+2 scenario replayed end-to-end through the fixed logic: the second
incorrect attempt now produces a note that explicitly blocks
agreement and demands the concrete walkthrough instead.

Side benefit, found while verifying: a bare numeric reply two turns
after an incorrect result (e.g. "4 and 5" after two wrong attempts at
3+2) is now also deterministically checked -- previously it fell
outside the one-turn `pending_challenge` window and was left to the
model's own arithmetic, even though it happened to be correct in that
transcript.

## Not yet done

No upper bound on how long `pending_challenge` can stay re-armed if
the child keeps mentioning numbers without ever landing on the right
one -- it only clears on a correct result or a turn with no number in
it at all. Low-stakes (worst case is one more escalating note, not a
crash or a wrong-but-confident claim), not revisited here.
