# 0092 — CHITTI_DISABLE_FACE must only suppress the idle face, not the whole screen

Date: 2026-10-23
Status: Accepted

## Context

Decision 0046's `CHITTI_DISABLE_FACE=1` skipped starting
`ScreenFaceDeviceController`'s render thread entirely, to A/B-test
how much the render thread's CPU contention affected timing on the
Pi's single core. Set it on the Pi per a direct request to measure
that -- the very next session surfaced a real gap in that request
and this toggle's actual effect: *"first problem im not able to see
the words on screen. i asked u to disable only face and not the
display of words."*

Confirmed in code: Reading Partner's reading-text, hint spotlight,
and word-family grid all render through that exact same thread --
skipping its startup to suppress the idle dot-matrix pattern also
silently removed every one of those, which was never the ask.

## What shipped

**`voice_loop_demo.py`**: the render thread now always starts
(`await face.start()` unconditionally) -- the env var no longer
controls whether the thread runs at all.

**`device/screen_face.py`**: new module-level `_FACE_DISABLED` (read
from `CHITTI_DISABLE_FACE` once, same pattern `audio/real.py` already
uses for its own env vars). The render loop's dot-matrix-face branch
(reached only when no spotlight/word-grid/reading-text is set) is now
`elif not _FACE_DISABLED:` instead of a bare `else:` -- when the flag
is set, that one branch draws nothing (leaves the background) instead
of the eye/mouth pattern; every other branch (spotlight, word grid,
reading text) is untouched and renders exactly as before, since they
were never the thing meant to be measured.

## Consequences

New test: `test_disabled_face_still_renders_reading_text` -- with
`_FACE_DISABLED` monkeypatched True, the render thread stays alive
with nothing shown (no spotlight/grid/reading-text set yet, the exact
state that used to draw the dot face), and still renders correctly
once `set_reading_text()` is called.

Full suite: 613 passed (4 failures in `test_screen_face_rendering.py`
-- the 3 pre-existing ones plus this new test, all the same root
cause: no usable SDL video driver in this dev environment, confirmed
by the identical log line in all four. Not a regression from this
fix.)

## Not yet done

The Pi's `.env` already has `CHITTI_DISABLE_FACE=1` set from the
original request to measure render-thread cost -- this fix changes
what that flag actually does (narrower scope) but the value itself
wasn't touched here, so the next session on the Pi will already be
running with eyes suppressed, reading text intact, without any
further action.
