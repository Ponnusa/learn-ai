# 0093 — Whole story on the TV, centered; log what the screen is actually showing

Date: 2026-10-23
Status: Accepted

## Context

Two related requests after moving Chitti's HDMI output to an actual
TV: *"print the words that are being shown in the hdmi. so the logs
can be bit clear to you for making any decission"*, and *"now we will
use hdmi, so we can show the whole story on the tv display. so center
it... no need to show line by line, as we have large space."*

## What shipped

**Screen-state logging** (`device/screen_face.py`): `set_reading_text()`,
`set_reading_spotlight()`, and `set_word_grid()` each now log what
they were just told to show (or that it was cleared), via the same
`logging` module the render loop's own frame-timing line already
uses. Added at the device layer, not at each `voice_loop_demo.py` call
site, so every caller -- present and any added later -- is covered
automatically; nothing to remember to add per call site.

**Whole story on screen** (`voice_loop_demo.py`, v1's
`_run_reading_partner()`): `face.set_reading_text(sentences, ...)` is
now called once, with every sentence in the passage, right before the
per-sentence capture loop begins -- not per sentence inside it.
Removed every per-sentence set/reset/clear call that used to cycle
the display one sentence at a time (including the ones in the
post-hint reread step): decision 0053's original reason for showing
just one sentence at a time was a small screen, which no longer
applies on a TV, and decision 0088 already made the per-sentence
resets pointless on their own (they existed to keep a now-removed
timed highlight in sync, not to change what was shown). Cleared once
with everything else when the whole passage finishes. The render
loop's own priority order (spotlight/word-grid override reading-text
whenever they're set) already handles the hint ladder's spotlight and
the word-family grid correctly on top of this without any extra
logic -- they were never affected by the per-sentence reading-text
churn in the first place.

**Centering** (`device/screen_face.py`'s `_draw_reading_lines_static()`):
each line is now centered horizontally (computed from its own
rendered width), not pinned to the left margin -- the vertical
centering of the whole block was already in place from decision 0088.

## Consequences

Four existing tests updated for the new, much simpler
`face.reading_texts` shape (the whole passage shown once, not per
sentence) -- including a rename
(`test_run_reading_partner_shows_and_captures_one_sentence_at_a_time`
-> `..._shows_the_whole_story_but_captures_one_sentence_at_a_time`) and
one whose own premise changed: the resumed-session test used to
assert the already-read first sentence was "never reshown" -- now
showing the whole story (including what's already been read, for
context) on a resumed call is the deliberate, correct behavior, not a
regression, so that assertion was rewritten to check what the test
actually cares about (the capture resumes at the right sentence), not
what's on screen.

Full suite: 613 passed (4 failures in `test_screen_face_rendering.py`
-- unchanged from decision 0092's baseline, all the same root cause:
no usable SDL video driver in this dev environment).

## Not yet done

The whole story is shown as plain text with no indication of which
sentence is currently being read/captured -- the console/speech
already carries that (and now the new logging makes it checkable
after the fact too), but nothing on screen itself distinguishes the
current sentence from the rest of the story. Not asked for; worth
considering if it turns out to matter on the TV in practice.
