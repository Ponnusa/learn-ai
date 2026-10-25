# 0112 — Keep the story on screen, and give the word game a real combined conversation

Date: 2026-10-25
Status: Accepted

## Context

Direct feedback after watching a real Reading Partner session:

> "we will show the full story always. dont remove it from screen...
> also when chitti plays a word game, then can it remove the letters
> directly in the story and highlighting the word directly in the
> story view rather than a separate view with only that word... also
> case of the letter should be preserved. wat happens when child
> gives answers i think it doesn reach the openai. right now it juts
> says for the answer ok got it.. but no feedback or no engagement...
> no need to go for each word as separate conversation, both missing
> word in same conversation."

Confirmed against the real code, five separate things:

1. `_run_reading_partner()` cleared the story (`face.set_reading_text(None)`)
   right after read-aloud/correction finished, before comprehension
   questions and the word game ran -- the child answered both blind.
2. The word game's own `face.set_reading_spotlight(blanked)` call
   replaces the full-story view entirely (`screen_face.py`'s render
   loop is a strict spotlight > word_grid > reading_lines priority
   chain) -- a separate, context-less view, one isolated word at a
   time.
3. `pick_game_words()` fed `blank_vowels()` an already-lowercased
   word, so "Sam" blanked to "s_m", not "S_m".
4. `reading/word_game.py`'s own docstring said "No LLM call" --
   decision 0057's deliberate original choice. Reactions came from
   two tiny fixed pools (3 lines; one template) -- never an LLM call
   at all, which is exactly the "ok got it, no feedback" being
   described.
5. The game ran one full ask-capture-react exchange PER word (up to
   2), not the combined single conversation asked for.

## What shipped

**Screen persistence** (`voice_loop_demo.py`): removed the
mid-book `face.set_reading_text(None)` between the read-aloud
finishing and comprehension questions/the word game running. The
story now stays visible from the start of a book until the mode's own
`finally:` block (leaving Reading Partner, or moving to a new book)
-- untouched, still the right place to clear it. The hint ladder's
own per-sentence narrow-then-widen behavior (decision 0095) is a
separate, already-correct mechanic, not touched.

**Multi-word highlighting, in context** (`device/screen_face.py`):
generalized the stored reading-text highlight from a single
`(sentence_index, word_position)` to a `set` of them.
`set_reading_text_highlight()` (the existing, live-speech one-word-
at-a-time setter) now wraps its single position into a 1-item set --
every existing caller works unchanged. New
`set_reading_text_highlights(positions)` (plural) sets several at
once, for the word game's own static case. `_draw_reading_lines_static()`'s
matching generalized from an equality check to set membership; same
default red highlight color as before.

**Case-preserving, in-context blanking** (`reading/word_game.py`):
`blank_vowels()` now blanks directly into the word's own original-
case text (`decompose()` already cleans internally for grapheme
matching, and for these simple alphabetic words its spans line up
1:1 with the original string either way) -- "Sam" -> "S_m". New
`find_word_occurrence(pages, clean_target)` locates a word's real
`(page_index, word_index, original_text)` on the actual story pages.

**One combined turn, one real reaction** (`_run_word_game()` in
`voice_loop_demo.py`, `reading/word_game.py`, `conversation/service.py`):
every picked word (still `pick_game_words()`, up to 2) is now blanked
in place within a copy of the story and all of them highlighted
together (`set_reading_text_highlights()`) -- the full story stays
visible, both blanks and highlights shown at once, not a separate
view per word. ONE question covers every missing word; ONE capture
gets the answer; each word's correctness is still decided
deterministically (`is_correct_answer()`, unchanged) -- never left to
the model, same reasoning decisions 0083/0097 already established for
comprehension answers. New `build_word_game_reaction_prompt()` hands
the model each word's already-decided result (and, for a miss, the
real phonics breakdown text to state, not invent) and asks for ONE
warm, combined reaction; new `ConversationService.react_to_word_game_answer()`
calls it and screens the reply like every other spoken output in that
class. The real phonics-sound playback for any wrong word (decision
0070/0091) is unchanged. The story is restored (unblanked, highlight
cleared) afterward rather than cleared, per the first point above.

`reading/hints.py`'s `blend_breakdown()` and `_run_word_family_practice()`'s
own use of `word_game.incorrect_response()` (a *different* mode,
decision 0084) are untouched -- `incorrect_response()`/`_INCORRECT_TEMPLATE`
stay in `word_game.py` for that caller; only the missing-letters
game's own reaction moved to the LLM.

## Consequences

Two new tests in `test_screen_face_rendering.py` (the single-word
setter still wraps into a 1-item set; the new plural setter sets/clears
several at once) plus one smoke test for the render thread. Six new
tests in `test_word_game.py` (case-preserving blanking;
`find_word_occurrence()` finds the right page/word index and
original-case text, `None` for a word not on any page;
`build_word_game_reaction_prompt()` states correctness as a given
fact with the real phonics breakdown, singular vs. plural phrasing).
Two new tests in `test_conversation_service.py` for
`react_to_word_game_answer()` (returns the combined reaction; screened
for safety). Rewrote the three existing `_run_word_game` integration
tests in `test_voice_loop_demo_intent.py` for the new one-combined-turn
shape (blanked-in-story display, both positions highlighted together,
one LLM-generated reaction, story restored afterward) and added one
new test confirming the story is never cleared between a book's own
read-aloud finishing and the "want another?" prompt.

Full suite: 723 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment; one of this decision's own new smoke
tests joins that same list for the same reason, not a new issue).

## Not yet done

`_run_reading_partner_v2` (decision 0075, default off, confirmed via
the pasted log not what's actually running) never had comprehension
questions or the word game ported to it at all -- out of scope here,
untouched. No parent-facing control over the word game's own
difficulty/word count -- unchanged from before.
