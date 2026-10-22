# 0079 — Cap word-family stacking; don't lose the re-read offer to an unclear reply

Date: 2026-10-22
Status: Accepted

## Context

Three reports from a real session: *"it goes into loop. not really
good."*, *"why the story generation fails, i still dont understand
llm will be able to generate story whatever be the case, it cannot
fail"*, and *"if there is already read story from parent, i should be
able to go back to there and start from there."*

Traced each against the actual transcript and code:

1. **Not a loop, but a real stacking problem.** A sentence with
   several real misses (e.g. "hen" AND "pig" AND "had", all in one
   sentence) triggers the word-family check (decision 0066) for
   *every one* that resolves independently -- up to three separate
   four-word detours stacked back to back before the sentence was
   even finished. It reads exactly like a loop even though it
   terminates.
2. **A real misunderstanding worth correcting plainly, not a bug.**
   The LLM can always write *some* text; the hard part is every single
   word already fitting the exact, narrow set of phonics patterns
   this specific child has mastered so far -- ordinary English
   constantly needs patterns a beginning reader hasn't learned yet.
   Decisions 0076-0078 already mean the overall system cannot
   dead-end (LLM -> hand-written story -> guaranteed word-drill), but
   the diagnostic log from a failed LLM attempt was printing with no
   context, reading like something had broken.
3. **A real bug.** The re-read offer (decision 0068) is asked *once*
   per call; the reply "The little forg" (an attempt to start reading
   the story's own title back, not an answer to the yes/no question)
   has no "yes" or "no" in it, and `is_affirmative()` collapses that
   into the same flat `False` as an explicit decline -- permanently
   losing the one-time offer for the rest of that session over a
   reply that was never actually a "no."

## What shipped

**`voice_loop_demo.py`**: the per-sentence hint loop now tracks
`offered_word_family_this_sentence`, set after the first offer and
checked before every later one in the same sentence -- capped at one
word-family detour per sentence, still offered for whichever word
resolves first.

**`intent/router.py`**: new `classify_affirmative(text) -> bool | None`
-- the same word-order-sensitive yes/no walk `is_affirmative()`
already used, but returning `None` (not a hard `False`) when no
signal word of either kind appears at all. `is_affirmative()` is now
`classify_affirmative(text) is True`, identical behavior for every
existing caller. The re-read offer uses the tri-state version
directly: an explicit yes re-reads; an explicit no moves on for this
call; anything else (`None`) leaves the one-time flag unset, so the
*next* book cycle asks again instead of silently giving up.

**`scripts/reading_partner_text_demo.py`**: a small logging handler
prefixes decision 0076's own "book generation attempt failed"
diagnostic with `[internal, harmless -- falling back automatically]`
in the text harness specifically, so it reads as the recovered-from
diagnostic it is instead of an unexplained error.

## Consequences

New tests: `classify_affirmative()`'s tri-state behavior
(`test_intent_router.py`); a sentence with two independently-resolved
real misses only gets one word-family offer, not two
(`test_voice_loop_demo_intent.py`); an unclear reply to the re-read
offer doesn't consume it -- the next book cycle asks again
(`test_voice_loop_demo_intent.py`). All existing `is_affirmative()`
tests pass unchanged, confirming the refactor didn't alter its
behavior for any current caller.

Full suite: 592 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- The re-read offer, once truly declined (an explicit "no"), still
  only gets one more chance per call cycle if the child changes their
  mind -- there's no "actually, yes" recovery after an explicit
  decline, only after an unclear reply. Not reported as a problem;
  not addressed here.
- The annotated-warning handler is specific to the text harness --
  the real voice loop never surfaces this log to a child or parent in
  the first place, so no equivalent change was needed there.
