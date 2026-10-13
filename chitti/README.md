# Chitti — Companion Robot (child-safe AI companion)

Status: **Milestone 1 — device/audio foundation, built against mocked
hardware.** No Raspberry Pi 5 in hand yet. See
`docs/decisions/0005-milestone-1-device-audio-foundation.md` for what's
built, what's verified, and a consolidated list of everything still
undecided.

## What this is

A child-safe AI companion robot for ages under 12, targeting Finland
first then the EU, built on Raspberry Pi 5. Full product specification:
`docs/product_spec.md`.

This is a sibling project to `../pixel-ai/` (an AI desk companion for
students) in the same repository, but a genuinely different product:
different users (children, with mandatory parent/guardian controls),
different regulatory exposure (EU toy safety, GDPR, AI Act transparency,
RED/CRA — see `docs/compliance_plan.md`), and stricter architectural
rules (no LLM-authored safety policy, no LLM-authored answer-checking, no
LLM access to hardware control). `pixel-ai/` is used only as a design
reference, not a code source — see `docs/decisions/0001-milestone-0-scope.md`
for why nothing is copied directly.

## Current state

- No hardware in hand yet (Raspberry Pi 5) — `device/` and `audio/` have
  mocked implementations (`MockDeviceController`, `MockAudioTransport`)
  so everything below is developed and tested without it.
- `app.py` starts and shuts down cleanly (Milestone 1's own acceptance
  criterion) — mocked device comes online, status LED reflects state
  (including mute), shutdown stops playback and powers the mock device
  down. Run it: `scripts/run_local.sh`.
- `config/loader.py` validates YAML config files (fails fast on a
  missing `schema_version`) and env secrets (fails fast on a missing
  required variable) — same fail-fast philosophy as `pixel-ai/config.py`.
- 17 unit tests passing (`scripts/run_tests.sh`) covering config
  validation, device lifecycle, audio mute/capture/playback, and app
  start/shutdown. **Not run — no hardware**: anything involving a real
  mic, speaker, LED, or mute switch.
- `src/companion_robot/voice/` still has typed interface stubs only
  (`SpeechToSpeechBackend`, `SpeechRecognitionBackend`,
  `LanguageModelBackend`, `TextToSpeechBackend`) — Milestone 2, gated on
  the AI-backend benchmarking in
  `docs/decisions/0004-modular-pipeline-over-realtime.md`.
- `conversation/`, `safety/`, `education/`, `reminders/`,
  `parent_controls/`, `storage/` remain empty packages with docstrings
  stating which milestone fills them in.
- **Design pivot (decision 0002, refined in 0003)**: there's no graded
  Education Engine for the MVP — `conversation/` instead owns a
  Teachable-Friend persona (the child teaches Chitti, any topic,
  age/profanity-filtered, plus a safety-filtered repeat-after-me mode)
  and a Story Companion (narrates from a preloaded or parent-uploaded
  story, answers grounded in that transcript). Parent controls are a
  local, PIN-gated, LAN-only web UI with child-profile and story
  management. Wake word is picked by the child from a vetted shortlist.
  Multiple children can share one device, switched via a self-ID phrase.

## Setup

```bash
cd chitti
./scripts/setup_dev.sh   # pip install -e .[dev]
./scripts/run_tests.sh   # pytest tests/unit/
./scripts/run_local.sh   # starts the app against mocked hardware
```

## Documentation

Start with `docs/architecture.md` (module map + AI backend decision),
then `docs/risk_register.md` and `docs/decisions/` (five so far) for why
things are built the way they are. `docs/compliance_plan.md` and
`docs/privacy_data_map.md` track what's explicitly **not yet assessed** —
don't treat their presence as a compliance claim.

## Next step

Milestone 2 (voice conversation) needs the AI-backend benchmarking listed
in `docs/decisions/0005-milestone-1-device-audio-foundation.md`'s
deferred-decisions section — Finnish quality and real-hardware ASR
latency, neither measurable without a Pi 5 in hand.
