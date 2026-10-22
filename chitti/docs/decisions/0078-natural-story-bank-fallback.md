# 0078 — A hand-written, natural story bank, ahead of the word-drill

Date: 2026-10-22
Status: Accepted

## Context

Direct follow-up to a product-owner critique of a real session, which
(after I'd fact-checked several of its other claims against the actual
code and found them to be a misdiagnosis of a now-fixed visibility
gap, or describing a separation that already existed) landed on one
genuinely real point: decision 0077's guaranteed-decodable fallback is
honest but not satisfying. *"Fin fit fix fizz a."* is fully decodable,
but it reads nothing like a story. The critique's own recommendation:
*"If the generator cannot produce a suitable story after a bounded
number of attempts, use a known, prevalidated story rather than
displaying a failed or unnatural result."* Confirmed with the product
owner: build that story bank first, ahead of the other two smaller
fixes from the same critique (tighter comprehension-reaction wording,
answer-aware comprehension checking) that are still open.

## What shipped

**New module `reading/story_bank.py`**: 19 hand-written short stories,
organized by cumulative phonics budget level (every level in
`LEVEL_SEQUENCE` up to and including the one the story was authored
for) rather than per individual grapheme -- hand-writing natural prose
separately for all 72 graphemes isn't a sustainable scope, and a
level-scoped bank still gives real coverage.

Writing stories that are both natural *and* fully decodable at the
earliest, most restrictive budget (pure short-vowel CVC/VC words, with
no suffix at all -- so no third-person "-s" verb endings) turned out
to be genuinely hard by hand too, the same constraint-satisfaction
difficulty decision 0076 found the LLM struggling with. Solved by
iterating against the real decodability engine while drafting --
every draft was checked programmatically and fixed on the spot, not
guessed at and hoped for -- and by leaning on modal constructions
("Sam can run", not "Sam runs") the same way real decodable-reader
programs do, which sidesteps the missing suffix entirely.

`pick_story_bank_book(objective, *, sight_words=None, session_index=0)`:
re-verifies every candidate's decodability against the real engine at
call time (never trusts the authoring-time check alone, same
discipline every other verifier in this package follows); prefers a
story authored for the objective's own `target_level`, falling back
to any other qualifying story otherwise; rotates deterministically by
`session_index` for variety across sessions. Returns `None` if nothing
in the bank qualifies, so the caller falls through to decision 0077's
word-drill -- the final backstop, not the first resort anymore.

**`voice_loop_demo.py`**: both `_run_reading_partner()`'s and
`_run_reading_partner_v2()`'s `BookGenerationError` handling now try
`pick_story_bank_book()` before `build_deterministic_book()`. The
fallback chain is now three deep: LLM-generated (best, most
personalized) → hand-written natural story (good, pre-verified,
actually a story) → guaranteed word-drill (last resort) → never an
apology.

## Consequences

New `test_reading_story_bank.py` (6 tests): every story is decodable
at its own claimed level; every curriculum level has at least one
story; `pick_story_bank_book()` finds a match for **every** of the 72
real curriculum graphemes (not just the 9 levels in the abstract);
prefers an on-level story when one exists; rotates across session
indices for variety; is deterministic for the same index.

Renamed/updated two existing integration tests
(`test_voice_loop_demo_intent.py`): the decision-0077 fallback test
now confirms the story bank fires first (checking the spoken line
contains one of the bank's own titles, not the word-drill's "Word"-
shaped one); a new test forces `pick_story_bank_book` to return `None`
(simulating "the bank has nothing," which cannot happen for a real
objective in practice) to confirm the word-drill backstop still
catches it.

Full suite: 587 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

Two smaller items from the same critique, deliberately deferred in
favor of this one (per explicit prioritization):
- Comprehension-reaction wording can hedge ("really close," "something
  special") even when the child's answer was fully correct -- an LLM
  phrasing-quality issue, not a logic bug (the `resolved`/`needs_retry`
  status itself was correct both times in the reported transcript).
- No deterministic expected-answer check for comprehension questions
  -- correctness is entirely LLM-judged today. Feasible for factual
  questions with one concrete right word; not meaningful for genuinely
  open-ended ones ("how did it feel").

Within this decision's own scope:
- Only 2-3 stories per level (19 total) -- a child who fails
  generation repeatedly at the same level will see the same small
  rotation repeat. More variety is a straightforward follow-up (more
  hand-written stories), not an architecture change.
- The bank's stories don't incorporate the parent-set `interest`
  (e.g. "dinosaurs") at all, unlike decision 0077's word-drill (which
  flavors its title) or the LLM path's own theming -- a real story's
  title and content are harder to retrofit with an arbitrary interest
  after the fact without risking a decodability violation; not
  attempted here.
