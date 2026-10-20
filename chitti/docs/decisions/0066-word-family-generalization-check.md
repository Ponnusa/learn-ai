# 0066 — Word-family generalization check

Date: 2026-10-20
Status: Accepted

## Context

Product owner, in the same follow-up that produced the 0064-0067
roadmap: *"when a child speaks that sentence then our llm should
provide such words or sounds like word, so it will teach more.. like
he learns mat, then its easy to see if he knows these cat, sat, bat,
rat all are similary only some phonics change, so we can ensure that
the child knows."* Reading one word correctly after the hint ladder
proves the child decoded that one word -- it doesn't prove the
underlying phonics pattern generalized. A same-rime, different-onset
set (mat -> cat, sat, bat, rat) is a direct test of exactly that.

Generation needed an LLM (there's no fixed word list this product
maintains), but whether a candidate actually shares the target rime
and is decodable at the child's current level is a deterministic,
checkable fact -- not something to trust on the model's word. Same
discipline every other generation path in this package already
follows (`book_generation.py`'s decodability retry loop,
`comprehension.py`'s screen-and-drop).

## What shipped

**New module `reading/word_family.py`**:
- `extract_rime(word) -> tuple[str, list[GraphemeHit]] | None` --
  uses `decodability.decompose()`; onset is the first grapheme, rime
  is every grapheme after it. Returns `None` for a one-grapheme word
  (nothing to vary, e.g. "a").
- `build_family_prompt(word, rime_spelling, num_words=4) -> str` --
  same `WORD:`-per-line convention as every other generation prompt.
- `parse_family_words(reply_text) -> list[str]`.
- `verify_family_word(candidate, target_rime_graphemes, mastered_levels) -> bool`
  -- decomposes the candidate and requires its rime graphemes to
  *exactly* match the target's (not an approximate rhyme), and that
  it's decodable at `mastered_levels` via `is_word_decodable()`. A
  failing candidate is dropped, not retried -- there's no single "fix"
  for a bad rhyme the way there is for a decodability violation, so
  this follows `comprehension.py`'s simpler screen-and-drop shape, not
  `book_generation.py`'s heavier feed-back-and-retry loop.

**`ConversationService.generate_word_family(word, mastered_levels, age=None, num_words=4) -> list[str]`**:
builds the prompt, calls the LLM once, parses, drops the original
word itself and anything that fails `verify_family_word()`, then
screens survivors through `check_speech()` like every other spoken
output. Returns `[]` if `word` has no rime to vary or every candidate
fails -- the caller skips the activity gracefully, same precedent as
0 comprehension questions.

**`voice_loop_demo.py`**: new `_run_word_family_practice()` --
offered (via `is_affirmative()`, same gate as the word game) right
after a hint word resolves inside the existing hint-and-retry loop.
Triggered only when `stage < HINT_STAGES - 1` -- the same Gap B
distinction decision 0065 already draws between real decoding (an
earlier stage, sounded out after a cue) and an echo (the final stage,
where Chitti already said the word outright). An echoed word isn't
"fresh, confirmed evidence the skill generalized," so it doesn't
trigger the check. Not offered after every correctly-read word either
-- only a word that was actually missed and then independently
recovered, so a clean read never turns into an extra detour.

The call site builds the same decodability *budget*
`book_generation.py` itself wrote the book under --
`objective.mastered_levels` plus `objective.target_level` if it's not
already in there -- rather than the bare `mastered_levels`. Caught
before shipping: a brand-new profile's `mastered_levels` is `[]` until
something actually crosses the mastery threshold, so passing it
unmodified would have rejected every family candidate (even ones
built on the exact grapheme the child just read in the book Chitti
generated for them) as "undecodable."

## Consequences

New `test_word_family.py`: `extract_rime()` on a multi-grapheme word,
a word where the rime spans several graphemes, and a one-grapheme
word (`None`); prompt/parse round-trip; `verify_family_word()` accepts
a true rime match, rejects a different rime and a same-rime-but-
undecodable candidate (digraph onset without that level mastered),
and rejects a single-grapheme candidate.

`test_conversation_service.py`: `generate_word_family()` parses and
verifies candidates, drops a mismatched-rime one, drops the original
word itself, returns `[]` without ever calling the LLM for a
no-rime word, and returns `[]` when every candidate fails.

`test_voice_loop_demo_intent.py`: existing hint-resolution tests
(`..._resolved_on_the_very_first_retry`, the Gap A multi-miss test,
the Gap B final-stage test) all still pass unchanged -- their fake
LLM's fixed `"unused"` reply has no `WORD:` lines, so
`generate_word_family()` returns `[]` and the new activity is a
silent no-op in those tests, exactly the intended "nothing to offer"
degrade path. Two new dedicated tests close the full loop: `..._offered_after_independent_resolution`
(accepting the offer reads through both verified family words, each
getting a real correct-response line) and
`..._skipped_when_llm_gives_no_usable_words` (no offer spoken, no
extra capture, when nothing verifies).

Full suite: 504 passed (2 pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).

## Not yet done

- Sentence-by-sentence reading with a persistent position (decision
  0067) -- the last decision in the approved roadmap, not started yet.
- A decline-the-offer path (`is_affirmative()` returning False) isn't
  separately tested here -- the gate itself is exhaustively covered
  already by the word game's own decline test using the identical
  mechanism.
