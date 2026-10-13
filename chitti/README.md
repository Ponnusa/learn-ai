# Chitti — Companion Robot (child-safe AI companion)

Status: **Six real features built and tested (81 unit tests passing),
all verified end-to-end on real Pi hardware.** See
`docs/decisions/0015-sqlite-thread-safety-fix.md` for the latest, and
`docs/decisions/` (15 so far) for the full history.

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

- **Safety layer** (`safety/checks.py`, `tool_validation.py`): deterministic,
  offline screening (profanity, unsafe content, human impersonation,
  parent-secrecy, engagement manipulation) that runs on anything Chitti
  is about to say, plus tool-call allowlist + schema validation.
- **Memory Service** (`memory/repository.py`): SQLite-backed, scoped per
  `child_profile_id`, refuses to persist conversation context, expired
  records excluded from reads without an explicit purge.
- **LanguageModelBackend implementations** (`voice/openai_backend.py`,
  `claude_backend.py`): both working against real APIs. A Finnish
  benchmark (`scripts/benchmark_finnish.py`) ran live against both —
  see `docs/decisions/0012-finnish-benchmark-both-backends-complete.md`
  for the result (a first data point, not a final backend decision).
- **ConversationService** (`conversation/service.py`): Teachable-Friend
  and Story Companion, both screened through the Safety layer before
  anything is returned; repeat-after-me needs no LLM call at all.
- **Reminder Service** (`reminders/repository.py`): SQLite-backed,
  `due_reminders()`/`mark_fired()` for a future scheduler loop, correct
  DST handling for recurring reminders (verified against a real
  Europe/Helsinki transition).
- **Parent Controls** (`parent_controls/`): a local, PIN-gated web UI
  (`scripts/run_parent_controls.sh`) — PIN setup/login with proper
  password hashing, server-side rate limiting, hand-rolled CSRF
  protection, child-profile and story management, and per-child memory
  review/deletion. Verified end-to-end in a real browser against the
  real Pi, not just the test client.
- **`app.py`** starts and shuts down cleanly against mocked device/audio
  hardware, confirmed on real Linux/ARM hardware: Ctrl-C produces a
  correct clean shutdown, something Windows couldn't exercise at all.
- **81 unit tests passing** (`scripts/run_tests.sh`), confirmed on both
  the dev sandbox and a real Raspberry Pi. That Pi is the existing Pi 1
  B+ used for `pixel-ai/`, **not** a Pi 5 — useful for "does this run on
  real ARM/Linux at all," not for Pi 5 performance numbers.
- **A real bug found only by running the real server** (decision 0015):
  SQLite connections aren't usable across threads by default, which
  Flask's dev server does on every request — invisible to all 78 of the
  Parent Controls unit tests (which run synchronously in one thread via
  the test client), caught immediately by actually running it. Fixed in
  `storage/sqlite.py`, benefiting every repository in this codebase.
- `src/companion_robot/voice/interfaces.py` still has the full-duplex
  `SpeechToSpeechBackend`/`SpeechRecognitionBackend`/`TextToSpeechBackend`
  stubs — real ASR/TTS and the actual voice I/O loop are Milestone 2,
  still waiting on a Pi 5 and the remaining benchmarks below.
- Not built, and not verifiable without real network/radio hardware:
  mDNS discovery (`chitti.local`) and the first-boot WiFi setup-hotspot
  onboarding flow.

## Setup

```bash
cd chitti
./scripts/setup_dev.sh          # pip install -e .[dev]
./scripts/run_tests.sh          # pytest tests/unit/
./scripts/run_local.sh          # starts the app against mocked hardware
./scripts/run_parent_controls.sh  # the Parent Controls web UI, reachable on the LAN
```

For the Finnish benchmark, copy `.env.example` to `.env` and fill in
`OPENAI_API_KEY`/`ANTHROPIC_API_KEY` **locally, never pasted into
chat** (see risk register #17 for why this is called out explicitly),
then `python scripts/benchmark_finnish.py`.

## Documentation

Start with `docs/architecture.md` (module map + AI backend decision),
then `docs/risk_register.md` and `docs/decisions/` for why things are
built the way they are. `docs/compliance_plan.md` and
`docs/privacy_data_map.md` track what's explicitly **not yet assessed** —
don't treat their presence as a compliance claim.

## Next step

Real ASR/TTS and the actual voice I/O loop (Milestone 2) still need: a
real Pi 5 (not the Pi 1 B+ used above), native-speaker review of the
Finnish benchmark result, and the vendor child-directed-use policy check
(risk register #11).
