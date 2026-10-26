# 0115 — The brief-callout tier also highlights in the full story, not alone

Date: 2026-10-26
Status: Accepted

## Context

Direct follow-up, from the same real session log: "why rid, was
showing alone on the screen, then it should have been like from the
full story right?"

Confirmed: `_give_brief_callout()` (decision 0103's tier for a
flagged sentence that didn't make the session's limited full-
correction budget) called `face.set_reading_spotlight(word)` --
which, per `screen_face.py`'s own render-loop priority
(spotlight > word_grid > reading_lines), replaces the ENTIRE display
with just that one isolated word, hiding the full story. Decisions
0112 and 0113 already fixed this exact isolated-view pattern for the
word game and the full hint ladder, respectively -- `_give_brief_callout()`
was simply missed in that sweep. Its own docstring had already
*claimed* "the whole story stays visible throughout," which was true
of `set_reading_text()` but not of the spotlight call it actually
used underneath that claim -- a real, if accidental, documentation/
behavior mismatch, not just a missing update.

## What shipped

`_give_brief_callout()` now takes the sentence's own `sentence_index`
and `sentence` text, finds each named word's real position within it
(`find_word_occurrence()`, the same helper decisions 0112/0113
already use), and calls `face.set_reading_text_highlight(word,
sentence_index, word_position)` instead of `set_reading_spotlight()`
-- the word lights up in place within the still-fully-visible story,
cleared the same way afterward. Its own call site in
`_run_reading_partner()` already has both `sentence_index` and
`sentence` in scope, so no new plumbing was needed there.

## Consequences

One existing test, `test_give_brief_callout_names_each_word_without_a_hint_ladder`,
rewritten to call the new signature and assert
`face.reading_text_highlights` (the real in-sentence word positions)
instead of `face.spotlights`.

Full suite: 725 passed (the same handful of pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video
driver in this dev environment).

## Not yet done

Nothing else known to still use the isolated spotlight view for
story-sourced words -- `_run_word_family_practice()`'s own spotlight
use (decision 0084) is intentionally untouched, since those are
LLM-generated practice words that often aren't in the story text at
all.
