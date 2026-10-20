# 0074 — Reread the sentence and check word meaning after a hint

Date: 2026-10-20
Status: Accepted

## Context

Product owner pasted a detailed critique of a real session (the
"frog"/word-family log from decisions 0066/0073) arguing Chitti was
treating a single correct read as proof of both decoding *and*
understanding, and proposed a sequence: *"Try the parent's text →
identify a difficulty → give the smallest helpful hint → retry →
reread → check meaning → save progress."*

Checked the critique's claims against the actual code before acting
on any of it (several didn't hold up, others did):

- *"Chitti changes the activity without explaining why... never
  silently switch lessons"* -- not accurate: the word game and word-
  family activity both already ask explicitly and only proceed on a
  yes (decisions 0057/0066). Not changed here.
- *"Reading frog correctly doesn't prove the pattern generalizes"* --
  already the exact point of the word-family check (decision 0066,
  now real-word-verified per decision 0073); not a gap.
- *"Record the skill actually demonstrated"* -- already true: a word
  is only ever hinted if it was a real miscue in the first place
  (`pick_hint_words()`), and decision 0065's Gap B already excludes a
  told-the-answer echo from mastery evidence.
- The one genuinely missing piece: after a hint-ladder word resolves
  (or exhausts the ladder), nothing ever rereads the sentence as a
  fluency check, and nothing ever asks whether the child understood
  what the practiced word *means* in context -- the hint ladder and
  word-family check both evidence *decoding*, never comprehension.

Confirmed with the product owner before building: reread the
sentence, **and** anchor one comprehension question to the specific
word just practiced (not generic whole-story questions only).

## What shipped

**`reading/comprehension.py`**: new `build_word_meaning_question_prompt(sentence, word, age)`
-- asks for ONE question checking understanding of `word`'s meaning/
role in `sentence`, explicitly not whether it can be pronounced. Same
`QUESTION:`-line convention as `build_question_prompt()`, so
`parse_questions()` and `react_to_comprehension_answer()` both work
against it unchanged.

**`ConversationService.generate_word_meaning_question(sentence, word, age)`**
-- builds the prompt, calls the LLM once, screens the one candidate
through `check_speech()`, returns `None` if nothing usable comes back
(same graceful-skip shape as `generate_comprehension_questions()`).

**`voice_loop_demo.py`**:
- Extracted `_ask_and_react_to_question()` from
  `_run_comprehension_questions()`'s inline retry loop -- one capture-
  react-retry-once helper now shared by the whole-book comprehension
  phase (decision 0059/0062) and the new per-sentence check, instead
  of two copies that could drift apart.
- New `_run_word_meaning_check(sentence, word, ...)`: generates the
  anchored question, and if one came back, asks it via
  `_ask_and_react_to_question()` against just that sentence.
- Wired into the per-sentence loop (decision 0067): whenever a
  sentence needed the hint ladder at all (`if hint_words:`, regardless
  of whether every word was ultimately resolved), it now (1) gets
  reread once, whole, with a flat "Nice reading!" acknowledgment --
  deliberately not graded again, since the hint ladder's own evidence
  already captured the decoding work; this is a fluency consolidation
  step, not a second scored attempt -- then (2) one word-meaning
  question anchored to the *first* hinted word in that sentence (one
  question per sentence, not one per hinted word, so a sentence with
  several misses doesn't turn into a drawn-out quiz).

## Consequences

New tests: `build_word_meaning_question_prompt()`'s prompt content
(`test_reading_comprehension.py`); `generate_word_meaning_question()`
parses/screens/degrades gracefully (`test_conversation_service.py`);
two `test_voice_loop_demo_intent.py` integration tests --
`..._rereads_and_checks_meaning_after_a_hint` (full flow: hint
resolves, word-family check runs first and finds nothing, reread,
question asked, wrong answer gets one clue, retry resolves) and
`..._skips_the_word_meaning_check_on_a_clean_read` (no hint word this
turn -> no reread, no question, only the whole-book comprehension call
happens).

Six pre-existing tests with a real miscue (hint retry success/
exhaustion, multi-miss, Gap B final-stage, both word-family tests)
needed one extra scripted capture each for the new reread step.
Two of those also had fixed-index `tts.synthesized[N]` assertions
spanning the new LLM-backed step; replaced with membership/search
assertions, since `_generate_with_thinking_filler()`'s escalating
filler lines (decision 0050) make the exact line count after any real
LLM call timing-dependent, not just content-dependent -- confirmed by
running the affected tests five times in a row with no flakiness
after the fix, versus a latent fragility the fixed indices had been
masking all along.

Full suite: 538 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- The reread itself is never graded or fed into mastery evidence --
  deliberately, per the "not a second scored attempt" reasoning above.
  If the product owner wants the reread to also count toward fluency
  tracking later, that's a separate, explicit decision, not implied
  by this one.
- Still only one word-meaning question per sentence, anchored to the
  *first* hinted word specifically -- a sentence with multiple real
  misses only gets comprehension-checked on one of them.
- STT-confidence-based "ask again if unsure" (another item from the
  same critique) is not addressed here -- the current
  `SpeechRecognitionBackend.transcribe()` interface returns plain
  text with no confidence signal at all; adding one is a larger
  interface change across every caller, not a small follow-up.
- "Clearly-labelled pretend-word decoding" (also from the critique) is
  not built -- a deliberate, specialized technique, not something
  broken today, and not confirmed as wanted yet.
