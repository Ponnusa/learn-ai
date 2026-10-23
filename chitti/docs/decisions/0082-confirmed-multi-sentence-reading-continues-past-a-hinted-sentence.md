# 0082 — Confirmed: multi-sentence reading continues past a sentence that needed the full hint flow

Date: 2026-10-23
Status: Accepted (investigation, no code change)

## Context

A transcript of "Dan and the Dog" (5 lines/sentences) was reported as
getting stuck on sentence 1 ("Dan had a big dog.") and never reaching
the rest of the passage, after that sentence needed the hint ladder
for two words ("had", "big"), a word-family detour, the post-hint
reread, and the word-meaning check.

## What was checked

The per-sentence loop itself (`for sentence_index in range(start_index,
len(sentences))` in `_run_reading_partner()`) is a plain `for` over
`range(...)` — nothing in its body re-assigns or decrements
`sentence_index`, or `continue`s back to the same iteration. Structurally
there is no mechanism for it to repeat sentence 1.

Reproduced the same shape as a test: a two-sentence passage where
sentence 1 needs a hint, triggers a (candidate-less) word-family
check, a reread, and a word-meaning question with one retry, then
confirmed sentence 2 is still shown and read
(`test_run_reading_partner_reaches_the_second_sentence_after_the_first_needed_the_full_hint_flow`,
`test_voice_loop_demo_intent.py`). It passes: `face.reading_texts`
shows sentence 1 (initial read), sentence 1 again (the reread's own
teleprompter call), then sentence 2 — in that order, nothing repeats
beyond the reread.

## What the transcript actually shows

The pasted log ends exactly here:

```
Chitti: That's a good guess! But remember, there was something special
about the dog that Dan had. Can you try again?

You (type what the child says):
```

This is the word-meaning check's own one-retry design
(`_ask_and_react_to_question(..., max_attempts=2)`, decision 0074): the
first answer ("dog") got `needs_retry`, so it's now waiting on
*attempt 2 of 2* — and whatever that second answer is, right or
wrong, the function returns right after it and the loop moves on to
sentence 2 immediately, same as the test above confirms. The
question itself isn't re-printed before that second prompt (only the
reaction text, "Can you try again?", appears) -- in the text-only
harness specifically, that can look like nothing is happening, when
it's actually just waiting on the final attempt before moving on
unconditionally.

## Consequences

No code change. New regression test added
(`test_voice_loop_demo_intent.py`) covering the gap this report
pointed at — a multi-sentence passage where sentence 1 needs the full
hint+reread+word-meaning-check treatment still reaches sentence 2 —
which wasn't previously covered (existing multi-sentence tests only
used clean reads).

Full suite: 600 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures).

## Not yet done

If the text harness's lack of a visible "last chance" cue before the
final retry attempt turns out to actually confuse testing sessions
(as opposed to just being the point where this particular transcript
was cut off), that's a legitimate, separate, small UX fix -- not made
here, since it wasn't confirmed to be needed.
