# 0057 — Post-reading "missing letters" word game

Date: 2026-10-18
Status: Accepted

## Context

Product owner wanted a fun bonus activity after Reading Partner's
verdict/feedback: a lightweight spelling game using words from the
story just read. Their example: the story contains "Japan" -> Chitti
shows "J_P_N" and asks the child to say the missing letters and the
whole word. Explicit requirements: explain the game clearly before
starting, don't force it, keep it light, and end on an encouraging,
funny note regardless of how it went.

**Reading of the example**: "J_P_N" blanks exactly the two vowels in
"Japan" (the A's), leaving every consonant visible -- "blank the
vowels, keep the consonants." Implemented by reusing
`decodability.decompose()`'s existing per-letter vowel/consonant
tagging (`GraphemeHit.kind == "V"/"C"`) rather than inventing new
segmentation logic, which also means a vowel *team* (e.g. "boat"'s
"oa") blanks as one unit, the phonics-correct granularity for this
curriculum.

Deliberately **not** part of the decoding-mastery assessment pipeline
-- `reading/mastery.py` and `reading/alignment.py` are untouched by
this feature, and nothing here feeds BKT or gets persisted. A single
attempt per word, no retry ladder like decision 0052's hints -- a
lighter, playful activity, not a graded one.

## What shipped

**New module `reading/word_game.py`** -- pure, deterministic, no LLM:
- `pick_game_words(words, max_words=2)` -- cleans each word, skips
  anything under 3 letters (same minimum decision 0056 just
  established for hints) or with no vowel-kind grapheme to blank,
  dedupes, returns the longest qualifying words.
- `blank_vowels(word)` -- `"japan"` -> `"j_p_n"`.
- `spell_out_blanked(blanked)` -- `"j_p_n"` -> `"J, blank, P, blank, N"`,
  a speakable version (underscores mean nothing read aloud).
- `is_correct_answer(word, spoken)` -- lenient on purpose: true if the
  target word appears anywhere in the reply (reuses
  `reading/alignment.py`'s `tokenize()`), so a child who spells the
  letters first and then says the word still gets credit.
- `random_correct_response()` / `incorrect_response()` /
  `random_closing_line()` -- fixed lines, same "deterministic
  rotation, no LLM" precedent as `voice_loop_demo._THINKING_FILLERS`.
  The closing line is always warm regardless of how the rounds went.

**`voice_loop_demo.py`**'s new `_run_word_game()`, called from
`_run_reading_partner()` right after the feedback line (decision
0055) and before the "want to try another one?" prompt (decision
0054). Offered, not forced: explains itself in one line and asks
"ready to play?", gated on the existing `is_affirmative()` (same
check `_confirm_switch()` already uses) -- a decline or unclear reply
skips the whole thing, no prompt wasted. If no word in the book
qualifies at all, the game isn't even offered. Each round reuses
decision 0053's `set_reading_spotlight()` to show the blanked word --
no new rendering code needed.

## Consequences

14 new tests in `test_word_game.py` (word selection, vowel-team
blanking, the Japan example itself, lenient answer matching). 3 new
end-to-end tests in `test_voice_loop_demo_intent.py`: declining plays
no rounds and never reveals/grades anything; accepting plays through
both picked words with correct/incorrect handling and always ends on
a closing line; a book with nothing qualifying never offers the game
at all. 5 pre-existing `_run_reading_partner` tests updated with one
more scripted capture (a decline) to account for the game now being
offered after every book in their fixtures. Full suite: 445 passed, 1
skipped (pygame unavailable in this dev environment, pre-existing).

## Not yet done

- Difficulty scaling tied to the child's phonics level -- always
  "blank the vowels," no easier/harder variants.
- Persisting game results anywhere -- purely a fun bonus.
- A visual letter-reveal animation -- the spotlight shows the static
  blanked word, same as decision 0053's existing display.
