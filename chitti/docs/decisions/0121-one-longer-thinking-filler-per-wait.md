# 0121 — Exactly one, longer thinking filler per wait

Date: 2026-10-26

Status: Accepted

## Context

Direct feedback after watching a real session log: during one LLM
wait, Chitti spoke three separate filler lines back-to-back before
the real reply. Decision 0117 fixed the OLD bug (always starting with
the exact same filler every time) by randomizing which lines play, but
kept the original escalate-up-to-3-lines-per-wait behavior from
decision 0050. Watched live, that still reads as stalling rather than
thinking -- only one filler is actually needed to bridge a typical
wait for the real reply.

## What shipped

**`voice_loop_demo.py`**: `_speak_while_thinking()` now speaks exactly
ONE filler per wait (`random.choice()` instead of `random.sample()`
over up to three), then waits silently for the real reply instead of
looping. `_MAX_FILLERS_PER_WAIT` is gone -- no longer meaningful with
only one filler ever spoken. The `_THINKING_FILLERS` pool's own lines
are each a bit longer now (e.g. "Hmm, let me think about that one for
a moment..." instead of "Hmm, let me think about that..."), so the
single filler alone comfortably bridges a typical OpenAI round trip
rather than finishing well before the real reply is ready.

## Consequences

Updated `test_voice_loop_demo_intent.py`:
- Removed the `_MAX_FILLERS_PER_WAIT` import (deleted constant).
- Renamed/rewrote `test_speak_while_thinking_stops_after_the_last_
  filler_when_still_not_done()` to
  `test_speak_while_thinking_never_speaks_more_than_one_filler()`,
  asserting exactly one filler plays for a wait that never resolves.
- `test_carried_over_text_gets_a_real_reply_without_another_capture()`
  and `test_fallback_tier_switch_declined_stays_in_current_mode()`
  both had fixed-length `_speak` mock `side_effect` lists sized for
  the old three-filler escalation (a `KeyboardInterrupt` placed after
  exactly that many calls, to stop the loop deterministically) --
  shrunk each list to match the new one-filler count, same pattern
  decision 0117 already had to fix for the same reason when the pool
  size changed.

Full suite: 713 passed (excluding the pre-existing, unrelated
`test_screen_face_rendering.py` failures -- no usable SDL video driver
in this dev environment).
