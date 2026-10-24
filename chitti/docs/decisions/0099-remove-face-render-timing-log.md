# 0099 — Remove the periodic face-render timing log

Date: 2026-10-24
Status: Accepted

## Context

Direct feedback: *"remove tis log : companion_robot.device.screen_face:
timing: face_render avg 62.5ms/frame over 75 frames (budget
66.7ms)"*.

Decision 0046 added this as a diagnostic, logged every ~5 seconds of
frames, specifically to check whether the dot-matrix face rendering
(decision 0044) was contending for CPU with STT/TTS/API calls on the
Pi 1 B+'s single weak core. That question has long since been
answered by the many real-hardware sessions since, and the line is
now just noise in every session's log.

## What shipped

**`device/screen_face.py`**: removed the whole mechanism, not just
the log call -- `frame_start = time.monotonic()` (only ever used to
measure this), `frame_durations` (the rolling buffer), the averaging
+ `logger.info(...)` block, and the now-unused
`_FRAME_TIMING_LOG_INTERVAL` constant. The render loop itself is
unchanged otherwise.

## Consequences

No tests referenced this logging or the removed symbols. Full suite:
632 passed (4 pre-existing, unrelated `test_screen_face_rendering.py`
failures -- no usable SDL video driver in this dev environment;
`test_audio_real.py`/`test_claude_backend.py` flaked under
full-suite load this run, confirmed passing in isolation, same
known timing-sensitive baseline as prior decisions).
