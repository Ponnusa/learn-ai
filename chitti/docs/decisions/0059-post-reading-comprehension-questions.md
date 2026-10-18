# 0059 — Post-reading comprehension questions

Date: 2026-10-19
Status: Accepted

## Context

Product owner shared an example comprehension-check script (sample
questions like "What does the bunny see?" / "Why are the bunny and
the bird happy?", asked after the child finishes reading) and asked
for feasibility. Confirmed via AskUserQuestion: build it for **both**
LLM-generated books and parent-uploaded exercises (decision 0052).

This is architecturally different from everything else in `reading/`:
every other grading mechanism (`alignment.py`'s `assess()`,
`hints.py`, `word_game.py`) is a deterministic diff against an exact
expected string. An open-ended "why are they happy?" has no single
correct string to diff against -- grading it exactly isn't the right
tool for the job. Rather than inventing fragile keyword-matching, this
reuses the pattern Story Companion already established
(`conversation/service.py`'s `story_companion_reply()`/
`build_story_companion_prompt()`, decision 0017): ground an LLM
response in *only* the story's own text, and react rather than grade.

**Deliberate precedent change, stated plainly**: decision 0052's
parent-uploaded exercises previously never touched an LLM at all --
the whole point was trusting the parent's exact text, no generation,
no decodability check. Comprehension questions need the LLM to *ask
about* that text, even though the text itself still isn't generated
or rewritten. This is a new LLM-touches-exercise-content surface,
screened via `check_speech()` same as every other LLM output in this
codebase (see new risk register row below).

**Default**: comprehension questions run unconditionally after every
book (both sources), not gated behind a yes/no like decision 0057's
word game -- this is framed as finishing the story, closer to decision
0051's own original intent, not an optional side activity. 1-2
questions per book, asked after the feedback line and before the word
game (talk about the story, then play).

## What shipped

**New module `reading/comprehension.py`** (prompts + parsing only, no
LLM call itself -- same split `reading/book_generation.py` already
uses between its own prompt/parser and `ConversationService` holding
the real backend call): `build_question_prompt()` (asks for a mix of
factual recall and one gentle "why"/feelings question, grounded in
"use ONLY what's in the story text below," strict `QUESTION:`-per-line
reply format matching `book_generation.py`'s `TITLE:`/`PAGE:`
convention), `build_reaction_prompt()` (asks for ONE short, warm
reaction, explicitly "not a grade, not correct/incorrect"), and
`parse_questions()` (strict line parser, same shape as
`parse_story_draft()`).

**`ConversationService`** gains two methods, next to
`generate_decodable_book()`: `generate_comprehension_questions()`
builds the prompt, calls the LLM, parses, then screens *each*
question independently through `check_speech()` and drops any that
fail -- no retry loop (unlike `generate_decodable_book()`'s verifier
loop; an open-ended question has nothing to "fix and retry" the way a
decodability violation does). Returns `[]` if every question gets
dropped. `react_to_comprehension_answer()` builds its prompt, calls
the LLM, and returns `self._screen(reply_text)` -- identical screening
to every other conversational path in this class.

**`voice_loop_demo.py`**'s new `_run_comprehension_questions()`,
called from `_run_reading_partner()` right after the feedback line
(decision 0055) and before `_run_word_game()` (decision 0057). Both
the question-generation call and each reaction call go through
`_generate_with_thinking_filler()` (decision 0050), same latency-
camouflage treatment every other AI call in this mode already gets.
If question generation returns `[]`, the function returns immediately
with nothing spoken and no extra capture consumed -- same graceful-
skip shape decision 0057's word game already established.

## Consequences

5 new tests in `test_reading_comprehension.py` (prompt grounding,
question parsing including the no-questions case). 5 new tests in
`test_conversation_service.py`: question parsing, dropping one unsafe
question among several, returning `[]` when every question is unsafe,
a reaction grounded in the real story text, and the reaction's own
`check_speech()` screening. 3 new end-to-end tests in
`test_voice_loop_demo_intent.py`: questions asked and reacted to for
an LLM-generated book; the same flow for a parent-uploaded exercise
(proving the precedent-change decision is actually wired through);
graceful skip when no questions parse. One pre-existing exercise test
updated -- it asserted "the LLM is never called" for an exercise,
which is no longer quite true (it's now called for comprehension
questions, just never for book generation/rewriting) -- narrowed to
check specifically that no book-generation call was made. Full suite:
460 passed, 1 skipped (pygame unavailable in this dev environment,
pre-existing).

## Not yet done

- Any actual *grading* of comprehension answers (right/wrong, tracked
  anywhere) -- reaction only, nothing persisted, no mastery signal.
- Comprehension questions during the hint-and-retry or word-game
  phases -- only the main post-feedback turn.
- Gating comprehension questions behind a yes/no like the word game --
  deliberately unconditional.
