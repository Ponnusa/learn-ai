# 0122 — The hint-word retry accepts the word inside a full-sentence echo too

Date: 2026-10-26

Status: Accepted

## Context

Found live in a real session log: twice, a child correctly retried
the missed word "nap" by repeating the whole sentence back ("Sam can
nap.") rather than just the bare word. Both times Chitti responded
with "That's okay! The word is 'nap'. Let's keep going!" as if the
retry had failed, even though the child clearly said the right word.

Traced to decision 0116's hint-word loop in `_run_reading_partner()`:
it judged the retry with `clean_word(attempt) == clean_word(hint_word)`
-- a strict equality. `clean_word()` strips punctuation and lowercases
but never tokenizes, so `clean_word("Sam can nap.")` is `"sam can
nap"`, never equal to `"nap"` alone. Any retry that wasn't the bare
single word, no matter how clearly correct, was marked wrong.
`reading/word_game.py`'s own `is_correct_answer()` already solves
exactly this shape ("don't penalize extra talk") for the missing-
letters game, with a lenient "the target word appears anywhere in the
reply" check -- the hint-word loop just never reused it.

(Separately, in the same log, one retry transcribed as "Nah." for a
spoken "nap" -- that's Whisper mishearing the child's actual speech,
not a logic bug; there's no story-text or exact-match signal available
here the way `reading/comprehension.py`'s own safety net has, so
nothing to fix for that one.)

## What shipped

**`voice_loop_demo.py`'s hint-word loop** (inside `_run_reading_partner()`):
now uses `is_correct_answer(hint_word, attempt)` (imported from
`word_game.py`, already used elsewhere in this same file) instead of
the strict `clean_word(attempt) == clean_word(hint_word)` equality,
for both the "resolved?" check and the word-family-practice trigger
that follows it. Result stored once (`got_it`) and reused for both,
instead of repeating the same comparison expression twice.

## Consequences

Added `test_run_reading_partner_hint_retry_succeeds_when_echoed_back_
in_a_full_sentence()` to `test_voice_loop_demo_intent.py` -- a retry
of "a cat sat" (the whole sentence, not just "sat") after a miss now
gets "There you go!", not the "word is X" miss response.

Full suite: 714 passed (excluding the pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).
