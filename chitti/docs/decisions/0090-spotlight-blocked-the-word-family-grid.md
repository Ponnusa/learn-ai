# 0090 — The hint-ladder spotlight was blocking the word-family grid

Date: 2026-10-23
Status: Accepted

## Context

Follow-up to decision 0089's render-thread resilience fix, which
turned out not to be the actual cause: *"the word list is not shown,
but the next sentence from the story was shown. so im definitly sure
that it doesn show at all."*

That one fact ruled out decision 0089's crash theory outright -- a
dead render thread would have frozen the *next* sentence's text too,
not just the grid. The render thread was alive and working the whole
time; something else was wrong.

Traced the actual call sequence: `_run_word_family_practice()` (which
calls `screen_face.py`'s `set_word_grid()`) is invoked from inside the
hint ladder's `for hint_word in hint_words:` loop, at the exact moment
a word has just resolved -- while `face.set_reading_spotlight(hint_word)`
from the *start* of that same word's hint attempts is still active.
The spotlight isn't cleared until the whole `hint_words` loop finishes,
which happens *after* `_run_word_family_practice()` returns. The render
loop's own priority order (`device/screen_face.py`'s `_run()`) checks
`if spotlight_word is not None:` before `elif word_grid is not None:`
-- so for the entire word-family exchange, the screen kept drawing the
frozen hint word instead of ever switching to the grid. Not a crash,
not a timing fluke -- just the wrong state left set by the caller,
every single time this ran.

## What shipped

**`voice_loop_demo.py`**: `_run_word_family_practice()` now calls
`face.set_reading_spotlight(None)` immediately before
`face.set_word_grid(family_words)`, clearing the blocking state itself
rather than relying on every call site to remember to do it first.

## Consequences

New assertion in the existing word-family test, using a new unified
`display_calls` log added to the test suite's `_FakeFace` (alongside
its existing per-method `spotlights`/`word_grids`/`reading_texts`
lists): confirms the spotlight's clearing call happens *before* the
grid-setting call in real call order -- not just "a None shows up
somewhere in the spotlights list," which wouldn't actually prove
anything about which one the render loop would have drawn at the
time.

Full suite: 607 passed (3 failures in `test_screen_face_rendering.py`
-- the 2 pre-existing ones plus decision 0089's new resilience test,
same cause as before: no usable SDL video driver in this dev
environment).

## Not yet done

This is the one call site that currently uses `set_word_grid()`. If a
second one is ever added, it will need the same
`set_reading_spotlight(None)` discipline -- not generalized into the
device layer itself here, since `screen_face.py`'s own render-loop
priority order (spotlight > word grid > reading text > face) is a
deliberate design already, not a bug to fix at that layer.
