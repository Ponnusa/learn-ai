# 0100 — A missed word-family word showed nothing on screen

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback, from a real hardware log: during word-family
practice, the child read "bat, hat, sat" correctly but missed "mat."
Chitti said "Good try! The word is 'mat' -- 'm' like in 'mat', 'a'
like in 'cat', 't' like in 'top'. Let's keep going!" -- but the
screen showed the story's sentence the whole time, never "mat"
itself.

Traced in `_run_word_family_practice()`: `face.set_word_grid(None)`
clears the grid right after the reading is captured (line ~1448),
and nothing in the missed-word correction loop right after it
(`for family_word in missed: ... incorrect_response(...)`) ever set
any display of its own. With the grid cleared and no spotlight set,
the render loop fell through to whatever was already showing --
the per-sentence correction block's own narrowed sentence display
-- not the word actually being corrected.

## What shipped

**`voice_loop_demo.py`**, `_run_word_family_practice()`'s missed-word
loop: `face.set_reading_spotlight(family_word)` before each missed
word's correction is spoken, and `face.set_reading_spotlight(None)`
once the loop finishes -- the same spotlight-then-clear precedent
the hint ladder (decision 0053) already established for exactly this
"show the one word being corrected" need.

## Consequences

`test_word_family_practice_only_corrects_the_missed_word_not_every_word`
extended to assert `face.spotlights == [None, "bat", None]` -- the
leading `None` is decision 0090's own pre-existing clear of the hint
ladder's leftover spotlight before the grid is shown, unrelated to
this fix; the trailing `"bat", None` pair is new.

Full suite: 637 passed (4 failures in `test_screen_face_rendering.py`
-- unchanged pre-existing baseline, no usable SDL video driver in
this dev environment).
