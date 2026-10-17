# 0045 — Face expression test script

Date: 2026-10-17
Status: Accepted

## Context

Decision 0044's dot-matrix expressions couldn't be visually verified
on the dev machine (no pygame wheel for this Python version). Checking
them on the Pi meant running the full voice loop demo and talking
through each mode/state combination to trigger it -- slow, and some
combinations (e.g. Error/retry) aren't even reachable through normal
conversation yet. Product owner asked for a small script to display
each expression individually.

## What shipped

New `face_expression_demo.py`: a menu of 15 `(DeviceState, mode)`
combinations covering the 6 base states and the 4 conversation modes'
Listening/Speaking variants (plus Idle for music mode, whose mouth
override is otherwise easy to miss). Picking one calls
`set_status_led()`/`set_expression_mode()` directly and holds it on
screen; the menu reprints so another combination can be picked without
restarting. Reuses `ScreenFaceDeviceController` exactly as `voice_loop_
demo.py` does -- no new face-rendering code.

## Consequences

No new tests -- same reasoning as decision 0043's `intent_demo.py`:
a thin script with nothing new to unit-test, calling only already-
covered methods.

## Not yet done

Nothing deferred -- scoped test tooling, not a product feature.
