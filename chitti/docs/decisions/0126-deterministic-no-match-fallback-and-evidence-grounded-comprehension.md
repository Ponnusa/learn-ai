# 0126 — Deterministic word-game fallback when nothing matches, and evidence-grounded comprehension reactions

Date: 2026-10-26

Status: Accepted

## Context

User feedback on a real session, with a concrete improvement plan for
two issues:

**Issue 3 (word game confusing):** the child's answer ("debat.")
matched neither target word ("pat", "the"), and the combined LLM
reaction came out garbled -- "You found the word 'pat,' but it was a
little tricky since the real word was also 'pat.' And for 'the,'
remember it is simply 'the.'" Both words were correctly graded wrong
by `is_correct_answer()`; the model just had nothing genuinely right
to anchor a warm reaction to, and improvised badly.

The user's suggested fix (visible letter choices to pick from, with a
sound explanation afterward) was checked against the real hardware
and the project's own prior decisions before deciding what to build:
this Pi has no button, touchscreen, or any selection input at all
(`voice_loop_demo.py`'s own docstring: "since this Pi 1 B+ has no
physical button") -- every multi-choice interaction in this codebase
today is voice-only. And "explain the sound if needed" would partly
reverse decisions 0116/0118/0120, which deliberately removed phonics-
sound teaching from this flow. Asked directly: keep voice-only, no
phonics explanation, just fix the confusing reaction -- confirmed.

**Issue 4 (comprehension feedback):** "What can the pup do?" ->
"The pup can run." got a bare "Great job... nice work!" with no
explanation of why, and "How do Pat and the pup feel?" -> "happy"
(a reasonable guess, not something the story states) got treated the
same way as a factual answer. Checked against the code: short answers
like these were already accepted fine (no "needs a full sentence"
bug); the real gap is that `story_library.py`'s own pre-written
question/evidence pairs (e.g. `("Where did Sam sit?", "Sam sat at the
mat.")`) were being thrown away -- `_run_comprehension_questions()`
only ever kept the bare question, never the evidence sentence that
could ground a specific, "why this is right" confirmation. The user's
full recall -> evidence -> inference 3-question drill was explicitly
NOT built, since it would re-add the same "too many questions" problem
decision 0123 just removed a source of.

## What shipped

**Issue 3 -- `voice_loop_demo.py`'s `_run_word_game()`:** when none of
the target words are found in the child's answer, skips the LLM
reaction call entirely and speaks a fixed, deterministic line naming
the real words (`That's okay! The word(s) were "X" (and "Y"). Let's
keep going!`) -- the same "nothing matched" precedent
`_run_word_family_practice()` already established (decision 0089).
The LLM reaction is still used whenever at least one word was
correct, where it has something real to react to.

**Issue 4 -- `reading/comprehension.py`'s `build_reaction_prompt()`:**
new optional `evidence_sentence` parameter. When given (a
story_library.py question's own evidence line), the prompt tells the
model to point a correct confirmation at that real story line. When
not given, the prompt tells the model this is an open-ended question
with no single right line -- a sensible answer gets encouraged as
good thinking, not confirmed as something the story states outright.
Threaded through `ConversationService.react_to_comprehension_answer()`
-> `voice_loop_demo.py`'s `_ask_and_react_to_question()` ->
`_run_comprehension_questions()`, which now keeps `book.comprehension`'s
own `(question, evidence)` pairs intact instead of discarding the
evidence half. LLM-generated (non-library) books still get
`evidence_sentence=None` for every question -- `generate_comprehension_questions()`
itself wasn't extended to produce evidence lines; see "Not yet done."

## Consequences

Added tests:
- `test_voice_loop_demo_intent.py`: `test_run_word_game_uses_a_deterministic_reaction_when_nothing_matched()`
  reproduces the exact log scenario -- the LLM's own programmed reply
  never appears, the deterministic fallback line does instead.
  `test_run_comprehension_questions_grounds_a_library_books_evidence_sentence()`
  constructs a `GeneratedBook` directly with a `comprehension` pair
  and asserts the evidence sentence reaches the actual prompt sent to
  the model.
- `test_reading_comprehension.py`: two new `build_reaction_prompt()`
  tests, one per branch (evidence given / not given).
- `test_conversation_service.py`: `test_react_to_comprehension_answer_passes_the_evidence_sentence_through()`.

Full suite: 717 passed (excluding the pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- `generate_comprehension_questions()` (the LLM-generated-book path)
  still never produces its own evidence line -- only story_library.py
  books get evidence-grounded reactions today. Extending the
  generation prompt to also emit a per-question evidence line (or
  `NONE` for genuine inference questions) is a reasonable follow-up,
  not done here to keep this change's risk and test surface small.
- The recall -> evidence -> inference staged question sequence from
  the user's original suggestion was deliberately not built, to avoid
  re-growing the total question count decision 0123 just cut down.
