# 0040 — Screen-based face display

Date: 2026-10-17
Status: Accepted

## Context

Chitti should show an animated face on the HDMI screen already
connected to the Pi (confirmed already in use for `pixel-ai`'s own
face code), reflecting conversation state -- state-driven
(idle/listening/thinking/talking), not emotion inferred from
content, per explicit product-owner confirmation. Screen-based was
confirmed over LED matrix hardware: no new purchases, matches this
project's established "software over new hardware" instinct (the
same reasoning behind push-to-talk instead of wake-word hardware).

**This maps directly onto an interface that already existed but was
never really implemented.** `device/interfaces.py`'s `DeviceController`
ABC already defines `set_status_led(state: DeviceState)`, and
`DeviceState` already has exactly the needed states (`IDLE`,
`LISTENING`, `PROCESSING`, `SPEAKING`, plus `MUTED`/`OFFLINE`/
`ERROR`). Only `MockDeviceController` existed before this (logs
transitions, no visual), wired into the separate, mostly-vestigial
`app.py` (Milestone 1 skeleton, no real conversation loop --
`voice_loop_demo.py` is where conversations actually happen, and it
used no `DeviceController` at all before this decision).

**Adapted, not copied, from a proven reference**: `pixel-ai/pixel_face.py`
is a real, hardware-tested pygame face already running on the same
Pi 1 B+ hardware class (its own comments confirm "cheap enough for a
700MHz ARMv6 core" and `/dev/dri/card0` present). Three hard-won
fixes carried forward:
1. SDL video driver fallback list (`kmsdrm`/`RPI`/`fbcon`/`fbdev`/
   `directfb`) -- Pi OS Lite has no desktop/X server, so SDL's
   auto-probe fails; which driver works isn't knowable in advance.
2. A real-hardware gotcha already solved there: if the kernel doesn't
   detect a display at boot, the fix is `hdmi_force_hotplug=1` in
   `config.txt`, not a driver-list change.
3. `SDL_AUDIODRIVER=dummy` before `pygame.init()` -- otherwise pygame
   opens a real ALSA device for `pygame.mixer` (unused here), which
   would contend with `audio/real.py`'s own `arecord`/`aplay`
   subprocess-based audio for the same device.

## What shipped

New `device/screen_face.py` -- `ScreenFaceDeviceController`, a real
implementation of the full `DeviceController` ABC (not just the
face-relevant parts, since nothing else implements it for real
hardware yet): `start()`/`shutdown()` spawn/join a daemon render
thread; `set_status_led()` is the only thing callers touch, updating
a lock-protected state; `emergency_stop()` is synchronous per the
ABC's own requirement; `health_check()` reports whether the render
thread is alive. The render loop draws simple eyes/mouth shapes per
`DeviceState` at ~15 FPS.

**pygame is imported defensively.** If it's missing entirely, or no
SDL driver works (no screen attached, an unexpected OS image),
`start()` logs a warning and the controller runs with no visible
face rather than raising -- confirmed necessary during
implementation itself: pygame has no prebuilt wheel yet for every
Python version (hit this on the dev machine, a very new Python
release), and a missing display library must never be able to take
down a real conversation session.

Wired into `voice_loop_demo.py` (not `app.py`) -- `main()` constructs
and starts the face alongside the other repositories, shuts it down
in the existing `finally` block. All three mode loops
(`_run_teachable_friend`/`_run_everyday_companion`/`_run_story_
companion`) call `set_status_led()` around their existing turn
structure (`LISTENING` before capture, `PROCESSING` before the LLM
call, `SPEAKING` before `_speak()`). `conversation/` itself never
touches `face` or `DeviceController` -- preserves the architecture's
explicit isolation requirement (the model has no path to device
state).

## Consequences

8 new unit tests (249 total passing, 1 skipped where noted below).
Split across two files on purpose: `test_screen_face.py` covers the
graceful-degradation path and holds regardless of whether pygame is
installed; `test_screen_face_rendering.py` covers the real render-
thread lifecycle against SDL's own `dummy` driver, gated behind
`pytest.importorskip("pygame")` so it skips cleanly (not fails) in
an environment without pygame, and runs for real wherever it's
actually installed (the Pi, per the new `pyproject.toml` dependency).

## Not yet done

Mood/emotion expressions beyond the four conversation states --
explicitly out of scope given the state-driven decision. Combined
real-world performance hasn't been verified: pixel-ai proved
rendering *alone* is cheap enough on this hardware class, but
rendering simultaneously with real STT/TTS API calls on the actual
Pi 1 B+ hasn't been tested together -- that's the manual verification
step, not something resolved by this decision.
