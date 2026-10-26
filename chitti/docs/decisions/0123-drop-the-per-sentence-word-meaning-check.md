# 0123 — Drop the per-sentence word-meaning check, kept the book's own comprehension questions

Date: 2026-10-26

Status: Accepted

## Context

Direct feedback after a real session log: a 4-sentence story with two
corrected sentences produced 4 separate questions back to back --
"What is the cat doing?" / "What can Sam do?" (decision 0074's
per-sentence word-meaning check, firing once per sentence that needed
the hint-and-retry loop), then "What does Sam have?" / "How do Sam and
the cat feel?" (decision 0059's book-level comprehension questions,
which run for every book regardless) -- before the word game even
started. That's a lot of back-to-back Q&A for one short story.

Asked which to cut: keep the book-level comprehension questions (they
run for every book already, and check understanding of the story as a
whole) and drop the narrower per-sentence word-meaning check, which
duplicated the same kind of check at a smaller scope.

## What shipped

**`voice_loop_demo.py`**: removed the call to `_run_word_meaning_check()`
that fired after a corrected sentence's reread, and the function
itself (its only caller). `_ask_and_react_to_question()` -- the
shared question/answer/retry helper both this and
`_run_comprehension_questions()` used -- is kept as-is for its
remaining caller.

**Dead code removed**, since this was the only caller:
`ConversationService.generate_word_meaning_question()` and its
`build_word_meaning_question_prompt` import; `reading/comprehension.py`'s
`build_word_meaning_question_prompt()`.

**Also fixed in passing**: the reread step's own single-word
correction (fired when the reread itself introduces a NEW miss) used
the same strict `clean_word(attempt) == clean_word(reread_miss)`
equality decision 0122 just fixed for the hint loop -- same bug, same
fix, now `is_correct_answer(reread_miss, correction_attempt)`.

## Consequences

Every book now gets at most the one set of book-level comprehension
questions (1-2, same as before) -- no more per-sentence questions on
top of that, regardless of how many sentences needed correction.

Updated tests:
- `test_reading_comprehension.py`: removed the
  `build_word_meaning_question_prompt()` test and import.
- `test_conversation_service.py`: removed the three
  `generate_word_meaning_question()` tests.
- `test_voice_loop_demo_intent.py`: `test_run_reading_partner_tiers_
  correction_by_weakest_tracked_mastery()` rewritten -- its scripted
  LLM replies and captures assumed a per-sentence word-meaning
  question for each of the two fully-corrected sentences; now reflects
  the single book-level comprehension pass (2 questions, answered
  after both sentences' own hint/reread steps finish, not interleaved
  between them). Updated a stale comment in
  `test_run_reading_partner_hint_retry_succeeds()` that misattributed
  the real LLM call after a reread to the word-meaning check instead
  of the book-level comprehension questions.

Full suite: 710 passed (excluding the pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

Total question count per session still isn't capped across sources
generally -- a longer book with more flagged sentences doesn't ask
more questions any more (that source is gone), but a book whose own
comprehension-question generation returns 2 is still 2, same as
always. Nothing further was asked for here.
