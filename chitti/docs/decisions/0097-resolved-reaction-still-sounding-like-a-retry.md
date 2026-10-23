# 0097 — A "resolved" comprehension reaction that still hedges

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback, from a real hardware log: Chitti asked "What did
the hen sit on?" against a story that literally reads "A hen sat on
a log." The child answered "Log." -- correct -- and Chitti replied
*"Great job! The hen did sit on something, but think about what that
something was again!"* and moved straight on to the next question,
never asking for a retry. The report: *"the child answered log
correctly but chitti didnt understand at all... context mixed up."*

Decision 0083 already added a safety net for this failure shape --
`answer_matches_story_text()` overrides the model's own verdict when
it wrongly marks a literal, story-grounded answer `needs_retry`. But
that override is gated on `reaction.needs_retry` being `True`. Traced
against the real story text and answer (confirmed via
`answer_matches_story_text("Log.", story_text)` returning `True` in
isolation), the live failure here was the *other* half of the same
contract: the model returned `STATUS: resolved` -- so the loop
correctly didn't ask for another attempt, consistent with the
observed transcript moving straight to the next question -- but its
own `SAY` text still read like an unresolved clue, contradicting its
own status. Decision 0083's override never triggers on a `resolved`
verdict at all, so this contradictory wording reached the child
verbatim.

## What shipped

**`reading/comprehension.py`**:
- `build_reaction_prompt()`'s guidance for both the "before the last
  attempt" and "last attempt" branches now explicitly says a right
  answer gets a clear confirmation and stops there -- "do not also
  hedge, add a clue, or ask them to reconsider." The two-line reply
  instruction now also tells the model its `STATUS` and `SAY` lines
  must agree with each other. A prompt change alone can't guarantee
  the model never contradicts itself again, so it's paired with a
  second deterministic check below rather than relied on alone.
- New `sounds_like_a_retry_invitation(text) -> bool`: a short,
  explicitly-non-exhaustive phrase list ("try again," "think about,"
  "what do you think," etc.) catching the common ways a reaction
  still invites another attempt despite being marked resolved.

**`conversation/service.py`**, `react_to_comprehension_answer()`:
the existing literal-match override now fires on
`reaction.needs_retry OR sounds_like_a_retry_invitation(reaction.text)`,
not `reaction.needs_retry` alone -- still gated on
`answer_matches_story_text()` first, so it only overrides when
there's already a cheap, deterministic reason to trust the child's
answer over the model's wording. A `resolved` reaction whose text is
already a clean, non-hedging confirmation is untouched (the existing
`test_react_to_comprehension_answer_grounds_in_the_story` test locks
this in -- the fix is additive, not a blanket override of every
resolved+matched reply).

## Consequences

One new test in `test_conversation_service.py` reproduces the exact
real transcript (story, question, answer, and the model's actual
contradictory reply) and confirms the override now fires. Three new
tests for `sounds_like_a_retry_invitation()` itself in
`test_reading_comprehension.py` (the real transcript's wording, a
few common phrasings, and a clean affirmation that must NOT trigger
it). No existing test changed.

Full suite: 621 passed (4 failures in `test_screen_face_rendering.py`
-- unchanged pre-existing baseline, no usable SDL video driver in
this dev environment).

## Not yet done

The phrase list in `sounds_like_a_retry_invitation()` is a backstop
for the specific wording shapes seen so far, not a general contradiction
detector -- a model reply that hedges in some other way entirely could
still slip through. If this resurfaces with different wording, it's
the same bug class and the phrase list is the place to extend, not a
sign the approach itself is wrong.
