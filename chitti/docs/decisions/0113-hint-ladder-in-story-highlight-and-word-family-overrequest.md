# 0113 — Hint-ladder correction stays in the full story; word family over-requests

Date: 2026-10-26
Status: Accepted

## Context

Direct follow-up to decision 0112's "keep the story on screen" fix,
applied one level deeper:

> "when a mistake is made in sentence, the sentence alone is shown.
> but i think here also the full story must be visible and when
> chitti reads only that sentence, only that sentence should be
> highlighted and as it reads the word highlight should move.. also
> at this point, when it tries to explain a single word, the same
> should be followed [...] not like only the incorrect word in the
> screen"

Confirmed against the real code (`_run_reading_partner()` in
`voice_loop_demo.py`): a flagged sentence's own correction block
(model-read, hint ladder, reread, word-meaning-check) narrowed the
display to just that one sentence (`face.set_reading_text([sentence],
...)`), only widening back to the full story once the whole block
finished. Within that block, explaining one specific missed word
narrowed further still, to an isolated `face.set_reading_spotlight(hint_word)`
view -- the same "separate view with only that word" pattern decision
0112 already fixed for the word game, just not here yet. A code
comment from decision 0098 explicitly documented *why* the display
was narrowed in the first place: the word-by-word highlight during
modeling was hardcoded to page index `0`, because "passing the real
sentence_index here matched nothing, since there was no other page to
match against" -- a deliberate fix for a problem this decision removes
outright.

Separately, confirmed: "when family practice is done, chitti doesn't
[say] all four words but only 2" -- `ConversationService.generate_word_family()`
asks the LLM for exactly `num_words` (4) candidates, but each one
must independently pass `verify_family_word()`'s strict filter (real-
word list membership, exact rime-grapheme match, decodable at the
child's level) with no retry or backfill at all if some fail -- a
common, expected occurrence that routinely delivered fewer than 4.

## What shipped

**In-story highlighting for the hint ladder** (`voice_loop_demo.py`):
removed the `face.set_reading_text([sentence], ...)` narrowing and its
matching "restore to the whole story" call at the end of the block --
the full story (already on screen per decision 0112) stays visible
the entire time. Both modeled reads of the flagged sentence
(`_speak_with_word_highlight()`, the up-front "Let's work on this
one" read and the later "I'll read it for you first" reread-prep
read) now pass the sentence's own real `sentence_index` instead of
the hardcoded `0` -- valid again now that the narrowing that required
it is gone. The hint ladder's per-word display
(`face.set_reading_spotlight(hint_word)`) and the reread-miss
correction's own spotlight (`face.set_reading_spotlight(reread_miss)`)
are both replaced with `face.set_reading_text_highlight(word,
sentence_index, word_position)` -- the word's real position, found
via `find_word_occurrence()` (from decision 0112's word-game work)
scoped to just the one known sentence, so a word repeated earlier in
the story can't be matched there instead.

`_run_word_family_practice()`'s own `set_reading_spotlight(family_word)`
use is untouched -- those are LLM-generated practice words that often
aren't in the story at all, so there's no "position in the story" to
highlight them at.

**Word-family over-requesting** (`conversation/service.py`):
`generate_word_family()` now asks the LLM for `num_words *
_FAMILY_OVERREQUEST_FACTOR` (2x) candidates up front -- still one
call, no retry round-trip -- absorbing the verifier's expected drop
rate. The result is still capped to `num_words` before returning,
unchanged.

## Consequences

Four existing `_run_reading_partner` tests in
`test_voice_loop_demo_intent.py` rewritten for the new behavior:
the two hint-retry tests now assert `face.reading_text_highlights`
(in-story highlight set/clear) instead of `face.spotlights`; the
multi-sentence test asserts the story is shown exactly once, never
narrowed, plus the hint word's real in-story position;
`test_run_reading_partner_highlight_uses_the_narrowed_display_page_not_the_story_index`
is renamed to `..._uses_the_real_story_index` and now asserts the
*real* sentence index (1, not 0) is what the modeled-read highlight
actually uses. Two new tests in `test_conversation_service.py`
confirm the over-request (the prompt asks for 8 when 4 are wanted)
and that the returned count still caps at `num_words` regardless.

Full suite: 725 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

The word-family over-request factor (2x) is a fixed constant, not
tuned against real drop-rate data -- if 2x still regularly falls
short in practice, a real retry-with-backfill loop (this decision's
"option 2," not chosen now) is the natural next step.
