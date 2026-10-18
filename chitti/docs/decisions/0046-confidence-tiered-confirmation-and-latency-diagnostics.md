# 0046 — Confidence-tiered switch confirmation + latency diagnostics

Date: 2026-10-18
Status: Accepted

## Context

Two separate requests, shipped together because they both touch
`_detect_switch_intent()`'s call sites.

**1. Confirmation for uncertain switches.** Discussed directly: for a
child-facing device, a silently *wrong* mode switch is worse than for
an adult user, especially mid-emotional-moment in Just Chat -- this
nearly happened for real ("my friend isn't talking to me" contains
"talk", one of the activity keywords). The strict-phrase tier
(`intent/router.py`'s `detect_intent_phrase()`) is unambiguous and
should keep switching immediately. The LLM-fallback tier
(`ConversationService.classify_intent()`) is a judgment call, not a
certainty, and deserves a quick check first.

**2. Latency diagnostics.** Replies feel slower since recent changes.
Three ranked hypotheses, none yet confirmed with real numbers: every
mode switch now re-runs session summarization (a real Claude call,
not just at true session end); the LLM-fallback intent tier may fire
on ordinary turns that merely mention "talk"/"chat"/"teach"; the
heavier dot-matrix face rendering (decision 0044) may be contending
for CPU with STT/TTS/API calls on the Pi 1 B+'s single core. This
decision adds timing logs to settle it with evidence, not more
guessing -- it does not change any behavior on its own.

## What shipped

**`intent/router.py`**: `is_affirmative(text) -> bool`, a deterministic
word-list yes/no parser (same pure-function style as
`detect_intent_phrase`). A negative word always wins over an
affirmative one in the same reply; an empty/unclear answer defaults to
`False` (don't switch) -- same safer-default instinct
`_pick_item_by_voice()`'s retry already uses.

**`_detect_switch_intent()`** now returns `(mode_code, confident)`
instead of just `mode_code`: `True` for a strict phrase match, `False`
for an LLM-fallback match or no match at all. New `_confirm_switch()`
speaks a one-line, mode-specific confirmation ("Sounds like you want
to hear a story -- is that right?") and returns `is_affirmative()` of
the spoken answer. Each conversational mode's switch check became:
```python
candidate_mode, confident = await _detect_switch_intent(text, conversation, "1")
if candidate_mode is not None and (
    confident or await _confirm_switch(candidate_mode, tts, audio, stt, face, speed)
):
    next_mode = candidate_mode
    switch_trigger_text = text
    break
```
A declined/unclear confirmation falls through to the existing normal
turn-processing code unchanged -- the original utterance gets a real
reply in the *current* mode, exactly as if nothing had been detected.

**Timing diagnostics** (`voice_loop_demo.py`): `setup_demo()` now calls
`diagnostics/logging_setup.py`'s existing `configure_logging()`
(previously only wired into `app.py`, so `voice_loop_demo.py`'s own
`logger.info()` calls were silently dropped -- no handler was
configured). A small `_timed(label)` async context manager logs one
INFO line (`"timing: <label> took X.XXs"`) per wrapped call, with
**no transcript text**, per that module's own existing logging
constraint. Wraps: `stt.transcribe()` specifically (not the
user-paced recording wait around it), TTS synthesis and audio playback
separately (synthesis is the real lag; playback is mostly just the
reply being read aloud in real time, per decision 0019), each mode's
reply-generation call, the intent-detection LLM fallback, and session
summarization (to directly test hypothesis #1, since it now runs on
every switch, not just session end).

**Face-render timing** (`device/screen_face.py`): each frame's actual
draw+flip duration (excluding `clock.tick()`'s own FPS-capping sleep)
is accumulated and logged as a rolling average once per ~5s window,
not every frame -- directly tests hypothesis #3.

## Consequences

8 new unit tests (297 total passing, 1 skipped where noted in decision
0040): `is_affirmative()`'s yes/no/unclear/negative-wins cases,
`_confirm_switch()`'s prompt and yes/no handling, an updated end-to-end
test proving a fallback-tier switch requires confirmation and that
declining gives the original utterance a normal reply in the same
mode (not a discarded turn), and `_timed()`'s logging behavior
(including that it still logs -- and re-raises -- on a failed call).

## Not yet done

The three latency hypotheses are **not resolved by this decision** --
only instrumented. Real numbers from a Pi session (ideally one that
includes at least one mode switch) are needed to actually rank them
and decide what, if anything, to fix. No behavior changes from the
diagnostics themselves.
