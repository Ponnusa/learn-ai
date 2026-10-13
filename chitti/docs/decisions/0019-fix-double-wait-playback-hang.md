# 0019 — Fix: playback effectively doubled its wait for longer clips

Date: 2026-10-13
Status: Accepted

## Context

Reported live: after Chitti finished reading a story, nothing
happened — no memory record appeared, and no "Press Enter to start
talking" prompt either. Looked like the program had hung.

## Root cause

`RealAudioTransport.play()` wrote the whole audio buffer to `aplay`'s
stdin pipe, then slept for the clip's *full* computed duration
afterward. That double-counts time for anything longer than roughly
the OS pipe's capacity (commonly ~64KB, under 2 seconds of this 24kHz
16-bit PCM format): `stdin.write()` already blocks close to real-time
for a longer clip, since `aplay` only drains the pipe as fast as real
playback actually consumes it. So the write call alone already took
close to the full clip duration, and the extra sleep added a second,
near-equal wait on top — roughly doubling the real wait for a
multi-sentence story. `_remember_story_read()`'s memory write and the
next turn's prompt both come *after* that `await`, so neither had run
yet; the program hadn't hung, it just hadn't gotten there.

This explains both reported symptoms as one bug, not two: "the story
isn't logged" and "it's stuck after the story" both trace to the same
overlong `await _speak(...)` call for the story's full-length content.

## Fix

`play()` now times the write call itself (`time.monotonic()` before
and after) and only sleeps for whatever's left of the expected
duration, plus the existing buffer-drain grace period:

```python
remaining = max(0.0, expected_duration - write_elapsed) + _BUFFER_DRAIN_GRACE_SECONDS
```

This correctly covers both cases a single fixed value can't:
- A **short** clip (fits entirely in the OS pipe buffer) returns from
  `write()` almost instantly, long before it's actually finished
  playing — still needs to wait close to the full duration.
- A **long** clip (write blocks near real-time due to pipe
  backpressure) has mostly already finished playing by the time
  `write()` returns — only needs the short grace period, not another
  full duration.

2 new unit tests prove both cases explicitly (mocking `time.monotonic`
to simulate an instant vs. a real-time-blocking write, and asserting
on the actual value passed to `asyncio.sleep`, not just that it was
called) — the first version's 4 tests all mocked `asyncio.sleep`
entirely without checking its argument, so none of them would have
caught this.

## Consequences

2 new unit tests (113 total passing). No change needed to
`_remember_story_read()`/`_summarize_and_remember_session()` or the
prompt flow — they were always correct, just unreachable until the
overlong wait finished.
