# 0081 — The reread is actually checked, not blanket-praised

Date: 2026-10-22
Status: Accepted

## Context

A product-owner critique of a real "Ben and the Big Bus" transcript,
explicit about priority: *"If you fix only one thing first, fix the
target-versus-response loop: Chitti must know exactly which word the
child was meant to read, what the child actually produced, ... and
what the next helpful action should be."*

The transcript: the hint ladder resolved "can", then Chitti said
*"Let's read that sentence again from the beginning."* The child
read "He can hop on the **bug** bus" instead of "**big** bus" — a
brand new substitution, never hinted on. Chitti replied "Nice
reading!" regardless.

Confirmed directly in code, not just the transcript: decision 0074's
reread step (`voice_loop_demo.py`, inside `_run_reading_partner()`'s
per-sentence hint loop) captured `reread_attempt` and printed it, but
never called `assess()` on it at all — the "Nice reading!" line was
unconditional, with nothing upstream of it that could have changed
it. "Not graded again" (0074's own stated intent, meaning "don't feed
this into mastery evidence a second time") had been implemented as
"not even looked at," which is a different and wrong thing.

The same gap exists in Reading Partner v2's analogous step
(`session_state.py`'s `FINAL_REREAD`, decision 0075) — there it's
even quieter: `final_reread_attempt` is captured and then nothing is
said at all before moving to comprehension. No real transcript
exercised this path yet (v2 doesn't have the word game or word-family
features the "Ben and the Big Bus" session used), but it's the same
bug in the same shape, so it's fixed alongside v1 rather than left for
a future report.

## What shipped

**`voice_loop_demo.py`, v1's reread step**: the captured
`reread_attempt` is now run through `assess()` against the sentence
(same call shape as the main read-aloud and hint-ladder retries
already use). `hints.pick_hint_word()` on that new assessment decides
the reaction:
- No real miss → "Nice reading!" (unchanged for an actually-clean
  reread).
- A real miss → one short, bounded correction cycle for that specific
  word: spotlight it, "Let's look at this word again. Listen:
  {word}.", capture one more attempt, then either `'Yes, "{word}"!
  Nice fixing that.'` or `'Good try! The word is "{word}".'`. This is
  deliberately **not** the full 4-stage hint ladder again (it's a
  reread, not a fresh miss) and does **not** loop if still wrong — it
  resolves in one pass either way, so this can't become a second
  unbounded ladder. Like the original reread, this correction cycle's
  evidence is still not fed into mastery (same "not a second scored
  attempt" principle decision 0074 already established) — only the
  *response* changed, not what counts as grading.

**`voice_loop_demo.py`, v2's final-reread step**: same idea, scoped
down to match v2's more streamlined design (no second correction
cycle, since nothing in the actual report exercises that path for v2
yet): `final_reread_attempt` is now assessed against
`session.sentence`, and Chitti says either "Nice reading!" or "Good
effort reading that again!" — never silence, and never a claim the
reread was clean when it wasn't.

Both changes needed `pick_hint_word` (singular) added to the existing
`hints` import.

## Consequences

New tests: a v1 end-to-end case where the hint ladder resolves "can"
and the reread introduces a brand-new "big"→"bug" substitution —
confirms the correction cue, the "fixing that" response, and that
"Nice reading!" is never spoken for that sentence
(`test_voice_loop_demo_intent.py`). The existing four-miss test's
reread ("a cat mat", still wrong) now exercises the correction cycle
too, updated for the extra capture and the extra spotlight pair
(`test_voice_loop_demo_intent.py`). Two new v2 tests: the existing
clean-final-reread case now asserts "Nice reading!" is actually
spoken (previously nothing checked this), plus a new case confirming
a miscue-bearing final reread gets "Good effort reading that again!"
instead of silence (`test_voice_loop_demo_reading_partner_v2.py`).

Full suite: 599 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures — no usable SDL video driver
in this dev environment; a couple of `test_audio_real.py` timing
tests flake under full-suite load but pass in isolation, unrelated to
this change).

## Not yet done

This was deliberately scoped to the critique's own stated top
priority only. Not addressed here, and not yet decided whether/how
to: word-family timing relative to sentence consolidation; comprehension-
reaction specificity (pointing back to the sentence text, distinguishing
recall vs. inference questions); excluding proper nouns (e.g. a
character's name) from the word game's candidate pool; richer,
separated multi-dimensional progress tracking. The critique's "end of
activity, ambiguous yes" point was checked against the code and found
to already behave correctly (the "want another one" question's "yes"
means "continue reading," which is what the outer loop already does
by default) — not a bug, not changed.
