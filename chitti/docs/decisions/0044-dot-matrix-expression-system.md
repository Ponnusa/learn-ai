# 0044 — Dot-matrix expression system for the screen face

Date: 2026-10-17
Status: Accepted

## Context

Product owner shared a reference LED-dot-matrix robot face (circular/
curved eyes and mouth made of small individual dots) and a detailed
expression spec covering Listening/Thinking/Speaking/Idle plus
mode-flavored variants for Story/Music/Learning/Chat, explicitly
preferring restrained, state-driven animation over continuous motion:
"use the mouth as a stable emotional symbol, not an animated lip-sync
display," no spinners/loops, blinking rare and never during thinking.

The existing `ScreenFaceDeviceController` (decision 0040) didn't match
either axis: it drew solid filled-circle eyes and an ellipse mouth, and
animated continuously via `math.sin()` (a pulsing mouth height while
speaking, orbiting dots while thinking, a pulsing glow while
listening).

Confirmed via AskUserQuestion:
1. Mode (story/music/learning/chat) is a **second, independent** axis
   from the interaction state (listening/thinking/speaking/idle)
   already tracked -- a new `set_expression_mode()` call, not folded
   into `DeviceState`.
2. V1 scope: the four interaction states with mode overlays. Success
   and Error/retry flashes are deferred -- nothing in the conversation
   code currently signals either moment to the face layer.

## What shipped

**Dot-matrix pattern library** (`device/screen_face.py`): each eye/
mouth shape is a small ASCII-art grid (`"  ###  "`, `" #   # "`, ...),
rendered through one shared `_draw_pattern()` primitive instead of a
bespoke draw function per shape -- a `"#"` becomes a small filled
circle at that grid position. Five eye patterns (open ring, happy
curve, thinking, a thinking-alt variant, closed/blink) and three mouth
patterns (small smile, flat dots, open circle) cover every state this
pass needs.

**Pure, testable lookup**: `_resolve_expression(state, mode)` is a
plain function with no pygame dependency, checking `_MODE_EXPRESSIONS`
(mode-specific overrides) before falling back to `_BASE_EXPRESSIONS`
(per-`DeviceState` defaults). Deliberately sparse mode table: per the
spec's own observation that story/learning "can remain almost static,"
only `"music"` overrides anything (its mouth becomes an open circle
instead of the default smile) -- `"story"`/`"learning"`/`"chat"` reuse
the warm default rather than getting a bespoke expression per state.

**`set_expression_mode()`** -- added only to `ScreenFaceDeviceController`,
*not* to `device/interfaces.py`'s `DeviceController` ABC. Mode is a
rendering concept specific to this screen-based face, not a generic
device concept every future implementation (a real LED-matrix
controller, `MockDeviceController`) needs to support, and
`voice_loop_demo.py` already constructs `ScreenFaceDeviceController`
concretely, so no interface change was needed to call it directly.
Each of the four mode functions calls it once near their existing
banner print (`"learning"`/`"chat"`/`"story"`/`"music"`).

**Discrete, restrained animation, replacing continuous pulsing
entirely**: `_DiscreteTimer`, a small pure class (testable without
pygame or real time), tracks an occasional on/off state -- either
fully inactive or "held" for a fixed short duration, never
interpolated. Used for two things: an occasional blink (every 3-6s,
held ~150ms, only in Listening/Idle/Speaking -- never during Thinking,
per spec) and a rare thinking-eye shift (every 2.5-4.5s, swaps to the
alt thinking pattern for 0.4s, only in Processing). Speaking's mouth
is now the same static smile as everything else -- no more pulsing
height ellipse; "the voice does the work, not the mouth."

## Consequences

9 new unit tests (288 total passing, 1 skipped where noted in decision
0040): `_resolve_expression()`'s base/override/fallback behavior and
`_DiscreteTimer`'s on/off/reschedule timing in `test_screen_face.py`
(pygame-independent), plus a `set_expression_mode()` liveness test in
`test_screen_face_rendering.py` (pygame-gated).

## Not yet done

Success and Error/retry expressions (spec's remaining two states) --
deferred because nothing in `conversation/`/`education/math_check.py`
currently signals either moment to the face layer; wiring that in is
its own small follow-up, not guessed at here. Music mode's eyes stay
the default rounded shape rather than stylized note symbols, per the
spec's own fallback ("rounded eyes, if your LED layout supports
[notes]") -- a nice-to-have, not attempted this pass. No visual
verification was possible on this dev machine (no pygame wheel for
this Python version, same gap noted in decision 0040); manual
verification on the Pi is the real test.
