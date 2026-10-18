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

## Addendum (2026-10-18): what the first real Pi session found

Two real sessions on the Pi surfaced a confirmed bug in this same
decision's own confirmation flow, and gave the first real evidence on
the latency hypotheses.

**Confirmation-answer parsing bug, found live.** A real exchange:
Chitti asked "Sounds like you want to just chat -- is that right?"
after "My friend is not talking to me" hit the LLM-fallback tier. The
child answered "yes my friend is not talking to me my friend is not
talking to me" -- a genuine yes, repeated for emphasis. The original
`is_affirmative()` ("any negative word anywhere in the reply wins")
read this as a decline, because "not" appears later in the restated
complaint, even though "yes" opened the sentence. Fixed by walking the
words in order and returning on the first signal word, not scanning
the whole reply for a negative override -- position, not "negative
always wins", is what actually carries a yes/no answer in real speech.

**The answer was also being silently discarded.** Separately from the
misparse, `_confirm_switch()` never acknowledged the answer at all --
it was consumed purely as a yes/no signal, so a child who repeats
something for emphasis got no response to that specifically (only the
original trigger text got a real reply, via whichever path the
confirmation result led to). Fixed with a short, fixed, deterministic
acknowledgment ("Great, let's do that!" / "Okay, got it.") spoken
right after the answer -- deliberately not an LLM-generated response,
which would add another round-trip during what's already a
slower-than-usual interaction.

**Latency evidence so far**: hypothesis #2 (keyword gate over-firing)
is ruled out for the sessions observed -- the fallback tier fired
exactly once across two full sessions, and correctly. Hypothesis #1
(session summary on every switch) is confirmed real where it did
fire: one mode switch cost an extra, clearly separate ~6.3s
(`session_summary`) on top of everything else. Hypothesis #3 (face
render contention) shows a real, visible correlation -- frame times
spike (into the 70-80ms range against a 66.7ms budget) around the same
moments as the slower `tts_synthesize`/`reply_generation` calls -- but
not enough on its own to explain the full magnitude: `reply_generation`
(8-15s), `tts_synthesize` (6-8s), and `stt_transcribe` (5-7s) are
*consistently* running roughly 3-10x slower than this project's own
earlier Pi benchmark (decision 0012: 1-3.5s), which reads more like a
network/connectivity factor than ~20% local CPU contention alone.
Added a `CHITTI_DISABLE_FACE=1` env var (checked in `setup_demo()`,
skips starting the render thread only -- every `set_status_led()`/
`set_expression_mode()` call site is unaffected, just a no-op) so a
face-off session's timing logs can be directly compared against a
face-on one to isolate the render thread's actual contribution.

6 more unit tests (298 total passing, 1 skipped where noted in
decision 0040) for the `is_affirmative()` fix and the new
acknowledgment behavior.

## Not yet done

The three latency hypotheses are **still not fully resolved** -- #2 is
ruled out, #1 is confirmed where observed, #3 is suggestive but
unconfirmed as the dominant factor. A face-off/face-on comparison
(now possible via `CHITTI_DISABLE_FACE=1`) is the next concrete step,
along with a plain network-latency check on the Pi itself (e.g. timing
a bare request to the API host) to separate "CPU contention" from
"network conditions" as competing explanations for the still-
unexplained bulk of the slowdown. No behavior changes from the
diagnostics themselves.
