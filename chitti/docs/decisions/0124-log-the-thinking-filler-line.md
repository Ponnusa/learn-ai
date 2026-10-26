# 0124 — Log the thinking filler line too

Date: 2026-10-26

Status: Accepted

## Context

Asked directly: log Chitti's thinking-filler lines, same as every
other line it speaks, to make session logs easier to follow.

Every other `_speak()` call site in `voice_loop_demo.py` is preceded
by `print(f"Chitti: {text}")`, which is what shows up as a `Chitti:
...` line in the console/session log. `_speak_while_thinking()` was
the one exception -- it called `_speak()` directly with no `print`
first, so a filler played audibly but left no trace in the log. This
is why decision 0121's own investigation (same session) had to infer
from timing-log line counts alone whether one or three fillers had
played, rather than just reading it off the log.

## What shipped

**`voice_loop_demo.py`'s `_speak_while_thinking()`**: adds
`print(f"Chitti: {filler}")` right before speaking it, matching every
other call site in the file.

## Consequences

Added `test_speak_while_thinking_prints_the_filler_it_speaks()` to
`test_voice_loop_demo_intent.py`, using `capsys` to assert the printed
line matches the filler actually spoken.

Full suite: 711 passed (excluding the pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).
