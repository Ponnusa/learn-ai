# 0101 — Disable thinking-filler speech (cut OpenAI TTS call volume)

Date: 2026-10-24
Status: Accepted (temporary)

## Context

Direct request: *"for now comment speakwhilethinking"* -- following a
real 429 ("Too Many Requests") from OpenAI's TTS endpoint during a
live session, and a follow-up question confirming that decision
0050's thinking-filler lines ("Hmm, let me think about that...",
"Okay, just a little longer...", "Almost got it...") were NOT
cached -- every single occurrence, even though the text is always
one of the same 3 fixed strings, triggered a fresh, uncached
`tts.synthesize()` call to OpenAI. Over a session with several
LLM-backed waits (comprehension questions, word-meaning questions,
book generation), that's real, avoidable call volume.

## What shipped

**`voice_loop_demo.py`**, `_generate_with_thinking_filler()`: the
call to `_speak_while_thinking(task, tts, audio, face, speed)` is
commented out. The background task is still created and awaited
exactly as before, and the timing log still measures the real call's
own duration -- only the spoken filler during the wait is disabled.
`_speak_while_thinking()` itself is untouched (still directly unit
tested).

## Consequences

Two tests updated -- both patch `_speak` with a fixed-length
`side_effect` list sized to the number of `_speak()` calls expected
across a scripted scenario, which included 3 filler calls per
LLM-backed wait:
- `test_carried_over_text_gets_a_real_reply_without_another_capture`:
  `[None, None, None, KeyboardInterrupt]` -> `[KeyboardInterrupt]`
  (only the real reply's own `_speak` call happens now).
- `test_fallback_tier_switch_declined_stays_in_current_mode`:
  `[None, None, None, None, None, KeyboardInterrupt]` ->
  `[None, None, KeyboardInterrupt]` (confirmation + decline
  acknowledgment, then the real reply).

Full suite: 637 passed (4 failures in `test_screen_face_rendering.py`
-- unchanged pre-existing baseline, no usable SDL video driver in
this dev environment).

## Not yet done

Marked "temporary" -- this is the quick lever to pull right after a
rate-limit hit, not the real fix. The better fix (caching the 3
fixed filler strings' audio once and reusing it forever, discussed
but not yet built) would remove the TTS call entirely rather than
just the spoken fallback during a wait, and would also make the
filler play instantly instead of waiting on its own synthesis
round-trip. Worth doing regardless of whether filler speech is
re-enabled.
