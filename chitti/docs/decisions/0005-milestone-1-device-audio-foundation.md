# 0005 — Milestone 1: device/audio foundation, and the consolidated deferred-decisions list

Date: 2026-10-13
Status: Accepted

## Context

Product owner approved starting real implementation ("let's go ahead and
start building"), with an explicit request to document everything still
undecided so it can be revisited later rather than lost or silently
assumed. This record does both: (1) what Milestone 1 actually built, and
(2) a single consolidated list of every open item scattered across
decisions 0001-0004, so there's one place to check instead of four.

## What Milestone 1 built

Scope matches spec section 12's Milestone 1 deliverable list exactly,
built against **mocked hardware** since no Raspberry Pi 5 is in hand yet
(decision 0001):

- `companion_robot/device/interfaces.py` — `DeviceController` ABC +
  `DeviceState` enum (idle/listening/processing/speaking/muted/offline/
  error — the exact state set spec section 4 requires the system to
  distinguish).
- `companion_robot/device/mock.py` — `MockDeviceController`: software-only,
  logs every transition instead of touching GPIO.
- `companion_robot/audio/mock.py` — `MockAudioTransport`: software-only,
  drops fed audio immediately while muted (matching how a physically
  muted mic never digitizes audio in the first place — a real unit test
  caught the first version of this getting it wrong by buffering and
  replaying muted-period audio once unmuted).
- `companion_robot/config/loader.py` — extended with `load_yaml_config()`:
  fails fast if `schema_version` is missing from a config file.
- `companion_robot/diagnostics/logging_setup.py` — minimal structured
  logging setup. Deliberately minimal: there's no audio or child speech
  flowing yet, so there's nothing to redact in practice — real
  redaction discipline matters once Milestone 2+ introduces that data.
- `companion_robot/app.py` — `App` class + `run()`/`main()`: starts the
  mocked device + audio, reflects mute state on the status LED, shuts
  down cleanly on SIGINT/SIGTERM (Linux/Pi; no-op fallback on Windows
  dev machines, which don't support `asyncio.add_signal_handler`).
- `tests/unit/`: 17 tests covering config validation, device lifecycle,
  audio mute/capture/playback, and app start/shutdown — all passing.
  Verified: `python -m pytest tests/unit/ -v` (17 passed) and a direct
  `python -m companion_robot.app` run, confirmed clean start/shutdown
  with structured log output.
- **Not run — no hardware**: anything involving a real microphone,
  speaker, status LED, or mute switch. Spec instruction #16 requires
  saying this explicitly rather than letting it blend in with what was
  actually verified.

## Consolidated list of deferred decisions (check here first)

From decision 0001:
- Final AI backend/LLM choice — narrowed by decision 0004 to "which
  `LanguageModelBackend` for the modular pipeline," still needs Finnish-
  quality benchmarking before committing.
- `companion_robot` package name — now in active use by real code
  (this milestone's imports all depend on it); flag now if it should
  change, before more code accumulates on top of it.
- Who performs the legal/compliance review (spec section 14) — needs a
  qualified external specialist, not a coding agent.

From decision 0002:
- Final wake-word shortlist (exact candidate names) — not yet chosen.
- Exact alarm alert design (volume/sustain/snooze specifics) — Milestone
  3 concern, not yet designed.
- Whether "things Chitti learned from the child" (Teachable-Friend)
  ever becomes a durable, reviewable memory, or always stays
  session-only.

From decision 0003:
- Parent PIN recovery flow — explicitly left as "maybe needed," not
  decided either way.

From decision 0004:
- Benchmark `faster-whisper` on Pi 5 alone once hardware exists —
  `pixel-ai/local_stt_server.py`'s precedent needed a separate machine,
  so Pi-5-sufficiency is not assumed.
- Benchmark OpenAI vs. Claude text models on Finnish quality before
  picking one.
- Measure real first-response latency on the modular pipeline once
  built, against the spec's "~1 second" target.

No new deferred items surfaced while building Milestone 1 itself beyond
the Windows-vs-Linux signal-handling note above, which is already
resolved (documented, not blocking).

## Next step

Milestone 2 (voice conversation) is gated on the AI backend
benchmarking above — specifically Finnish quality and real-hardware ASR
latency — neither of which can happen without a Pi 5 in hand. Until
then, Milestone 1's foundation (config, diagnostics, device/audio mocks,
app lifecycle) is the stable base the rest builds on.
