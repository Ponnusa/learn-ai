# 0049 — Persistent HTTP sessions for every voice backend

Date: 2026-10-18
Status: Accepted

## Context

After decision 0047's `max_tokens` cap, a fresh Pi session gave the
real test: `intent_detection_llm_fallback` (capped to `max_tokens=10`
-- a single word) still took 5.74s, essentially unchanged from the
5.19-5.64s seen *before* that cap existed. If response length or
prompt size were the driver, capping output to 10 tokens should have
made that call nearly instant. It didn't move at all -- a payload-
independent floor, present even on a near-empty response, is the
signature of fixed per-call overhead, not generation time.

All four voice backends (`openai_backend.py`, `claude_backend.py`,
`tts_openai.py`, `stt_openai.py`) called the bare module-level
`requests.post(...)` function. That's a well-known `requests` pitfall:
the convenience function creates a brand-new, throwaway `Session`
internally on every single call -- no HTTP keep-alive, no TCP/TLS
connection reuse across calls, even to the same host seconds apart.
On a connection with any real round-trip latency, DNS + TCP handshake
+ TLS handshake, repeated on *every* call regardless of how small the
request or response is, could easily account for several seconds --
matching exactly what was observed across all four backends uniformly.

Also discussed directly: does reusing a `Session` risk getting stuck
on a closed/stale connection? No -- `urllib3`'s connection pool (what
`requests.Session` is built on) already handles a server closing an
idle keep-alive connection transparently, opening a fresh one as
needed on the next call. A connection that dies mid-request is a
different, pre-existing situation (an actual exception, not retried by
default) that exists identically with or without this change -- not
something this decision needed to solve to deliver the latency win.

## What shipped

Each of the four backend classes now constructs one `requests.Session()`
in `__init__` and calls `self._session.post(...)` for every request,
instead of the bare `requests.post(...)`. Nothing else about the
request shape, payload, or error handling changed. Retry-on-failure
logic was considered and explicitly **not** added in this pass --
it's a reliability improvement, not a latency one (a retry only
engages after a failed attempt, so it can only add time, never reduce
it), so it's a separate concern from what this decision set out to fix.

## Consequences

4 new unit tests (309 total passing, 1 skipped where noted in decision
0040), one per backend, proving the same `Session` object persists
across multiple calls on one instance -- the actual property this fix
depends on; a regression that silently created a fresh `Session` per
call would defeat the whole point without any other test noticing.
Existing tests across all four backend test files were updated to
patch `requests.Session.post` instead of the module-level
`requests.post`, since that's genuinely what's called now.

## Not yet done

Whether this actually explains the bulk of the observed slowdown is
still an open, testable question -- the next real Pi session's timing
logs will show directly whether `stt_transcribe`/`tts_synthesize`/
`reply_generation`/`intent_detection_llm_fallback` drop meaningfully.
If they don't, the remaining gap points elsewhere (still-unconfirmed:
plain network/WiFi conditions on the Pi itself, API-side load). Retry-
on-failure for a genuinely dropped mid-request connection remains a
real, separate reliability gap, not addressed here.
