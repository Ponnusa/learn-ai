# 0071 — Themed follow-up: decodability budget wins, with a plain fallback

Date: 2026-10-20
Status: Accepted

## Context

Same live session as decision 0070's bug report. After reading the
parent-uploaded exercise "THE LITTLE FROG" ("The frog jumps over the
log.") and playing the word game, the child asked for another one --
and got *"I'm having trouble coming up with a story right now..."*
instead of decision 0068's intended themed follow-up. Product owner's
complaint: *"the llm didn't do anything here. no extra sentences that
resemble the ones given by teacher was provided... is it because the
kid's age was set at 10?"*

Traced the actual failure: `age` only affects the prompt's *wording*
instruction ("for a child who is {age} years old") -- it never touches
the decodability *budget*, which comes entirely from the profile's own
per-grapheme mastery state (`objective.mastered_levels`/`target_level`),
independent of chronological age. So age=10 wasn't the literal bug --
but it did feed the real one: decision 0068's `source_passage` prompt
asked the model to reuse *"some of the same words"* from the parent
passage, and that passage ("frog", "jumps", "over") is never
decodability-checked at all (decision 0052 -- the parent is the
authorizing adult, so no check applies to parent-uploaded content).
"frog" needs blends, "jumps" needs blends *and* suffixes, "over" needs
r-controlled vowels -- none of that was mastered yet on a profile this
early. A capable model, told a 10-year-old's story should reuse this
vocabulary, kept trying to honor that over the strict budget below it
in the same prompt, burned every one of its `max_attempts` retries on
decodability violations, and `generate_decodable_book()` raised
exactly as designed when nothing safe and decodable came back in
time -- correctly implementing a prompt that was, in effect, asking
for two things in tension.

## What shipped

**`reading/book_generation.py`**: `_build_prompt()`'s `source_passage`
branch rewritten to make the priority explicit instead of implicit:
*"that passage was not checked against the decodability budget below,
so most of its own words are likely too advanced for it. Only reuse an
exact word from it if that word already fits the budget -- otherwise
invent new, simpler words with the same topic and feel. The
decodability budget below always wins over matching the passage's
exact wording."* Reusing the passage's topic/characters/setting is
still the ask; reusing its exact vocabulary is now explicitly optional
and subordinate.

**`voice_loop_demo.py`**: even with the tightened prompt, a themed
attempt can still fail (a sufficiently constrained budget, or a
passage with nothing simple to extract a topic from). The normal-
generation branch now tries `[source_passage, None]` in order when a
themed attempt is in play -- if the themed call raises
`BookGenerationError`, it retries ONCE more with no theming at all
(the plain, untethered generator) before actually giving the apology.
A themed follow-up is a nice-to-have; it was never worth ending the
whole session over when a normal book would very likely still
succeed.

## Consequences

New test in `test_reading_book_generation.py`:
`generate_decodable_book(..., source_passage=...)`'s prompt contains
the explicit budget-priority wording.

New test in `test_voice_loop_demo_intent.py`:
`test_run_reading_partner_falls_back_to_a_plain_book_when_the_themed_one_fails`
-- a fake LLM that always fails the themed attempt (returns an
undecodable draft whenever the prompt contains the source passage) but
always succeeds the plain one; confirms the session gets a real book
(and never the apology) instead of dead-ending.

Full suite: 529 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- The tightened wording reduces but can't eliminate the chance of a
  themed attempt failing outright (still LLM behavior, not a
  deterministic guarantee) -- the fallback-to-plain retry is the real
  safety net, not the wording alone.
- No change to `max_attempts` (still 4) for either the themed or plain
  attempt -- the fallback retry adds resilience across two *different*
  prompts rather than just giving the same struggling prompt more
  tries at itself.
- Still unconfirmed whether the *specific* live failure was purely the
  budget-vs-vocabulary tension described here or also involved some
  other model/backend hiccup -- not diagnosable further without the
  actual failing prompts/replies from that session, and the fix here
  (tightened prompt + fallback) addresses the mechanism either way.
