# 0119 — Warmer comprehension feedback, and spread the word game's picks across sentences

Date: 2026-10-26

Status: Accepted

## Context

Direct feedback after watching a real session:

1. When a comprehension answer is correct, Chitti sometimes just says
   "Thanks for sharing that!" -- flat and generic, doesn't feel like a
   real conversation. Traced to two causes: `build_reaction_prompt()`'s
   own guidance for a correct answer never actually asked the model to
   name the detail the child got right, so even a well-formed reply
   could land generic; and `parse_comprehension_reaction()`'s fallback
   for a malformed LLM reply (no `SAY:` line at all) was that exact
   hardcoded string, with no reference to what the child actually
   said.
2. The missing-letters word game's two picked words often sit right
   next to each other in the same sentence, which feels cramped --
   `pick_game_words()` just returns the story's two longest qualifying
   words with no regard for where they land, so a short story's
   longest words frequently collide in one sentence.

## What shipped

**`reading/comprehension.py`**: both correct-answer guidance branches
in `build_reaction_prompt()` (not-last-attempt and last-attempt) now
explicitly ask the model to name the actual detail the child got
right, not a generic acknowledgment. `parse_comprehension_reaction()`
takes a new optional `child_answer` parameter; its malformed-reply
fallback now reads `Great job, you said "{child_answer}" -- nice
work!` when an answer is available, instead of the flat, context-free
default.

**`conversation/service.py`**: `react_to_comprehension_answer()` now
passes `child_answer` through to `parse_comprehension_reaction()`.

**`voice_loop_demo.py`'s `_run_word_game()`**: pulls a larger candidate
pool from `pick_game_words()` (`_WORD_GAME_CANDIDATE_POOL = 8`, up from
the default of exactly `_MAX_GAME_WORDS` = 2) and keeps at most one
word per sentence when selecting the final picks, falling back to a
same-sentence pick only if there still aren't `_MAX_GAME_WORDS` enough
after exhausting distinct sentences -- e.g. a one-sentence story, where
spreading across sentences is impossible. `pick_game_words()` itself
is untouched (still the longest-qualifying-words-first selector); the
spreading logic lives in the caller, which is the only place that
knows about sentence placement.

## Consequences

Updated/added tests:
- `test_reading_comprehension.py`: fallback text now reflects the
  child's answer when one is passed.
- `test_voice_loop_demo_intent.py`: existing word-game tests
  (single-sentence stories) still pick both words via the same-sentence
  fallback; no new test added for the multi-sentence spread case since
  the existing two-sentence fixture (`test_run_word_game_matches_the_
  sentence_split_already_on_screen`) already happens to exercise two
  different sentences and continues to pass unchanged.

Full suite: 721 passed (same pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

The "name the real detail" instruction is still just a prompt-level
ask, not enforced -- if the model ignores it, the reaction will be
warm-but-vague rather than specific, same trust level as every other
LLM-phrased reaction in this flow.
