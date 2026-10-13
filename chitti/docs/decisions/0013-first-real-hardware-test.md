# 0013 — First real-hardware test: all 63 unit tests pass on Linux/ARM

Date: 2026-10-13
Status: Accepted

## Context

First time any of Chitti's code ran on real hardware rather than this
agent's Windows dev sandbox. The product owner ran it on their existing
Pixel AI Raspberry Pi (`chitti@LearnXAI`) — a Pi 1 B+, single-core
700MHz ARMv6, 512MB RAM, Raspberry Pi OS Legacy Lite (32-bit). This is
**not** the Pi 5 decision 0001 and the spec target — it's the much
older, weaker device already in use for `pixel-ai/`. Worth stating
plainly so later results aren't mistaken for Pi 5 numbers.

## What this confirms

- `pip install -e ".[dev]"` succeeded on real ARMv6/32-bit Raspberry Pi
  OS — all of `pyyaml`, `better-profanity`, `jsonschema`, `requests`,
  `python-dotenv`, and `tzdata` installed cleanly. Worth noting
  positively given this project's own history of real ARM wheel-
  availability problems elsewhere (`onnxruntime` had no ARMv6 wheels at
  all, hit earlier in `pixel-ai` work) — none of Chitti's current
  dependencies hit that wall on this device.
- `./scripts/run_tests.sh` → all 63 unit tests passed, matching this
  agent's dev-sandbox result exactly. Covers config validation, device/
  audio mocks, the Safety layer (including the `better-profanity`
  check), Memory Service (SQLite), both `LanguageModelBackend` mocked
  tests, ConversationService, and the Reminder Service's DST-crossing
  recurrence test — all correct on real Linux/ARM, not just Windows.
- `./scripts/run_local.sh` started cleanly, and **Ctrl-C produced a
  correct, clean shutdown** (`Chitti shut down cleanly`) — this
  resolves the open question from decision 0005: Windows has no
  `asyncio.add_signal_handler` support, so SIGINT/SIGTERM handling was
  never actually exercised until now. Confirmed working on the real
  target OS family (Debian-based Linux), not just assumed.

## What this does not confirm

- Anything about Pi 5 specifically — no such hardware has been tested
  yet (decision 0001's "no hardware yet" still stands for the actual
  target device).
- Any performance/latency characteristic — this device is dramatically
  weaker than a Pi 5, so timing numbers from it would misrepresent the
  real target and weren't measured here on purpose.
- ASR/TTS/voice I/O — none of that exists yet (Milestone 2, still gated
  on the AI-backend decision).

## Consequences

- `docs/decisions/0005-milestone-1-device-audio-foundation.md`'s "not
  run — no hardware" caveat is now partially superseded: hardware
  exists (the Pi 1 B+), and the app/test suite have run on it
  successfully. The Pi 5-specific gap remains open.
