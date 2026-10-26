# 0125 — The missing-letters word game skips sight words too

Date: 2026-10-26

Status: Accepted

## Context

Found live in a real session log: the word game picked "the" as one
of its two missing-letter words, blanking it to "Th_ pup can run."
and asking the child to read it back. A sight word is meant to be
recognized whole, not sounded out letter by letter -- blanking its
one vowel makes for a nonsensical puzzle, not a useful phonics check.

This is the exact same word, and exact same root cause, decision 0058
already fixed for the hint ladder: `reading/hints.py`'s
`is_worth_practicing()` excludes sight words
(`curriculum.DEFAULT_SIGHT_WORDS`) specifically because "the" passed
its plain length check and got selected there too. `word_game.py`'s
own `pick_game_words()` had its own separate, plainer length check
(`_MIN_WORD_LENGTH = 3`, no sight-word exclusion) that was never
updated to match -- the two activities drifted apart on what counts
as "a real word worth practicing."

(Separately, in the same log, the LLM's own word-game reaction text
was confusing -- "You found the word 'pat,' but it was a little
tricky since the real word was also 'pat.'" -- when the child's
actual reply ("debat.") matched neither target word. Both words were
correctly marked incorrect by the deterministic
`is_correct_answer()`; the model just phrased the wrong-answer
reaction oddly. Nothing to fix there -- phrasing quality on a
correctly-graded wrong answer isn't a logic bug.)

## What shipped

**`reading/word_game.py`**: `pick_game_words()` now uses
`hints.is_worth_practicing()` (length + not-a-sight-word) instead of
its own plain `len(word) < _MIN_WORD_LENGTH` check. `_MIN_WORD_LENGTH`
is gone -- `hints.py`'s own `_MIN_HINT_WORD_LENGTH` (same value, 3)
does that job now, from one shared place instead of two that could
drift again.

## Consequences

Added `test_pick_game_words_skips_sight_words_even_when_long_enough()`
to `test_word_game.py`, reproducing the exact word list from the real
session log -- "the" no longer gets picked even though it's 3 letters
and has a vowel to blank.

Full suite: 712 passed (excluding the pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).
