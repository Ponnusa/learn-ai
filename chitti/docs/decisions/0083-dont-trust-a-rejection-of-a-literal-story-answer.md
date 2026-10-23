# 0083 — Don't trust a model rejection of an answer stated verbatim in the story

Date: 2026-10-23
Status: Accepted

## Context

A real transcript caught a genuine grading error, not a misdiagnosis:

```
Chitti: What color is Dan's dog?
You: red
Chitti: Great try! But remember, the dog has a color more commonly
        found in nature. What do you think?
You: brown
Chitti: That's so close, but actually, Dan's dog is red! Great job
        paying attention!
```

The story's own text says "Dan has a red dog." The first answer,
"red," was exactly correct -- stated verbatim in the story -- and the
model rejected it anyway, with a clue ("a color more commonly found
in nature") that doesn't even point at red. On the forced-reveal final
attempt it then admitted "red" was right all along, after already
making the child guess again and get a second answer wrong.

Checked `react_to_comprehension_answer()` (`conversation/service.py`)
and `build_reaction_prompt()`/`parse_comprehension_reaction()`
(`reading/comprehension.py`): the entire correctness judgment is the
model's free-text call, with no story-grounded check of any kind
before trusting `needs_retry`. Unlike every other generation path in
this codebase (book generation, word family, decodability), there is
no deterministic verification step here at all.

A fully general, structured fix (have question-generation also emit
a known target answer/keyword, then grade against that
deterministically) would be a much bigger change touching
`generate_comprehension_questions()`'s return shape and every call
site in both v1 and v2. Not done here -- scoped instead to the
specific, demonstrated failure shape: the model rejecting an answer
that is *itself* sitting right there in the story text.

## What shipped

**`reading/comprehension.py`**: new `answer_matches_story_text(answer,
story_text) -> bool` -- true if any word 3+ letters long in `answer`
appears as a whole word in `story_text` (both sides cleaned via the
existing `decodability.clean_word`). Deliberately lenient: a shared
word is treated as "don't trust the model's rejection," not as proof
of correctness -- the failure this guards against (telling a child a
story-grounded answer is wrong) is worse than the one it risks (being
too easy on an answer that merely shares a word with the text),
matching this codebase's existing bias elsewhere (the hint ladder's
no-penalty retries, the word game's always-upbeat closing). New
constant `LITERAL_MATCH_AFFIRMATION`, a fixed, generic affirming line
-- deliberately not built from the model's own SAY text, since that
text was written on the assumption the answer was wrong and can
contradict the override outright (as in the transcript above).

**`conversation/service.py`**: `react_to_comprehension_answer()` now
checks `answer_matches_story_text()` whenever the model says
`needs_retry`; if it matches, the reaction is replaced with
`(LITERAL_MATCH_AFFIRMATION, needs_retry=False)` before screening,
regardless of what the model's own SAY text said. A genuinely
unrelated wrong answer (shares no real word with the story) still
gets the model's own retry handling unchanged.

Both `_run_word_meaning_check()` and `_run_comprehension_questions()`
(v1 and v2) go through this same function, so the fix applies
everywhere a comprehension-style question is reacted to, not just the
end-of-story comprehension step.

## Consequences

New tests: `answer_matches_story_text()`'s match/no-match/case-
insensitive/short-word-ignored cases (`test_reading_comprehension.py`);
`react_to_comprehension_answer()` overriding the exact reproduced
"red"/"nature" rejection, and still retrying a genuinely unrelated
answer ("purple") unchanged (`test_conversation_service.py`).

Full suite: 608 passed (1 pre-existing, unrelated
`test_screen_face_rendering.py` failure -- no usable SDL video driver
in this dev environment; this run didn't hit the other known-flaky
one from the same file).

## Not yet done

This is a safety net against one specific, demonstrated failure
shape, not a general fix for comprehension-answer grading quality --
the model can still misjudge an answer that doesn't share a literal
word with the story (e.g. a paraphrase, or an inference question with
no single right word at all). The bigger, structured fix (questions
carrying their own target answer, graded deterministically first) is
a real option if this keeps coming up, but wasn't built here.
