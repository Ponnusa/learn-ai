# Architecture — Milestone 0 proposal

Status: proposal, not yet built beyond typed interface stubs. See
`docs/decisions/0001-milestone-0-scope.md` for what this pass did and did
not implement.

## Relationship to `pixel-ai/`

Chitti is a separate product from Pixel AI (this repo's existing
`pixel-ai/` folder): different users (children under parent supervision,
not students), different regulatory exposure (EU toy safety, GDPR, AI Act
transparency, RED/CRA — see `compliance_plan.md`), and a stricter trust
model (no LLM-authored safety policy, no LLM-authored answer-checking, no
LLM→hardware control). Per the project owner's decision, pixel-ai is used
as a **design reference only** — no files are copied; chitti is written
fresh against this spec's module boundaries. The concrete patterns reused
and risks found are recorded in `docs/decisions/0001-milestone-0-scope.md`.

Chitti otherwise has **zero runtime dependency on `pixel-ai/` or the
LearnX backend** — different product, different data controller.

## Module map (spec section 3.2, services A–I)

| Spec service | Package | Milestone that fills it |
|---|---|---|
| A. Device Controller | `companion_robot/device/` | 1 |
| B. Audio Engine | `companion_robot/audio/` | 1–2 |
| C. Voice Interaction Engine | `companion_robot/voice/` | 2 |
| D. Conversation Service | `companion_robot/conversation/` | 3 |
| E. Memory Service | `companion_robot/memory/` | 3 |
| F. Education Engine | `companion_robot/education/` | 4 |
| G. Reminder Service | `companion_robot/reminders/` | 3 |
| H. Parent Controls | `companion_robot/parent_controls/` | 5 |
| I. Compliance and Diagnostics | `companion_robot/diagnostics/` | ongoing, this doc set is the start |

`companion_robot/storage/` is a cross-cutting repository-abstraction layer
(SQLite first, spec section 10) used by memory, reminders and parent
controls rather than a spec service of its own.
`companion_robot/config/` wraps validated configuration + env secrets
(spec section 9), extending `pixel-ai/config.py`'s fail-fast `_require()`
pattern.

## Voice architecture (spec section 4)

Five typed interfaces, defined now with method signatures and docstrings
only (`NotImplementedError` bodies) in `src/companion_robot/voice/` and
`src/companion_robot/audio/`:

- `SpeechToSpeechBackend` — a single full-duplex streaming backend (e.g.
  OpenAI Realtime).
- `SpeechRecognitionBackend`, `LanguageModelBackend`, `TextToSpeechBackend`
  — the modular ASR+LLM+TTS alternative, each independently swappable.
- `AudioTransport` — microphone capture / speaker playback, hardware-
  independent so it can be mocked before real Pi 5 hardware is in hand.

This mirrors `pixel-ai/pixel_openai_voice_semantic.py`'s proven streaming/
barge-in/turn-state shape, but that file has no backend abstraction at
all — it calls OpenAI directly. Chitti's interfaces exist so that shape
can be reimplemented behind a provider-neutral contract, per spec section
4's explicit requirement ("must not require a specific cloud provider").

### AI backend comparison (not a decision — compiled for review)

| | OpenAI Realtime | Claude pipeline (ASR+LLM+TTS) | Local/Moshi-style |
|---|---|---|---|
| Latency | Lowest — proven single-hop in `pixel_openai_voice_semantic.py` | Higher — 3 separate hops | Unproven on Pi 5 alone |
| Provider lock-in | High (no neutral realtime speech API elsewhere today) | Low per-hop (ASR/TTS swappable) | None — fully offline |
| Data residency | Leaves device to OpenAI (US) — EU residency/zero-retention terms unverified | Leaves device per-hop, terms vary by provider | Stays on-device — best fit for GDPR by construction |
| Finnish support | Claimed multilingual, quality/latency **unverified** | Depends on ASR/TTS choice, unverified | Weakest — most local real-time speech models are English-first |
| Commercial/child-use policy | OpenAI's child-directed-app policy not yet checked | Anthropic's not yet checked | N/A (no vendor policy; model licence still needs checking) |
| Engineering cost | Lowest — reuses proven plumbing shape | Medium — new pipeline, simpler pieces | Highest — most unknowns |

**Recommendation (not a decision):** build `SpeechToSpeechBackend`
provider-neutral from day one; prototype behind it with OpenAI Realtime
first for engineering velocity. Treat the spec's "offline/degraded mode"
(section 9) as a separate, much simpler fallback — canned local responses
with safety/mute/emergency-stop still live — not a full local-LLM swap-in.
Finnish-language quality and both vendors' child-directed-use policies are
hard blockers to verify before any real pilot, regardless of which backend
is eventually chosen.

## Safety boundary (spec sections 5 and 9)

Unlike `pixel-ai/pixel_teaching_prompt.py` (safety-adjacent behavior lives
entirely in the system prompt), chitti's `safety/` package must be real,
independently-testable application code that:
- Runs after every model response, before it's spoken, regardless of
  persona prompt content.
- Validates every tool-call's arguments against a fixed JSON schema
  before the `conversation/` service is allowed to execute it — no tool
  outside a hard allowlist exists, and none of them ever accept or `exec()`
  model-authored code. (This is the same reasoning already given to the
  user when they asked whether an LLM could write pygame animation code
  on the fly — the answer there was "don't `exec()` untrusted model
  output"; here it's a hard product requirement, not just advice.)
- Never has a path to GPIO, motor control or emergency-stop — those live
  only in `device/`, which the Conversation Service cannot reach directly.

## Education Engine boundary (spec section 7)

`education/` owns answer-checking as deterministic code. The
`LanguageModelBackend` may be asked to explain *why* an answer is right
or to phrase a hint, but the activity session's correctness state is
never written from a model response — this is the opposite of every
existing pixel-ai teaching path, all of which are fully generative with
no answer-checking engine at all.

## Memory Service (spec section 6)

`memory/` defines a versioned record type now (`MemoryRecord` dataclass:
`id`, `category`, `content`, `created_at`, `updated_at`, `expires_at`,
`source`, `consent_or_authorization_status`, `retention_policy`,
`schema_version`) with no storage logic yet. This supersedes
`pixel-ai/pixel_memory.py`'s flat Markdown upsert/append file, which has
no consent, retention, expiry or deletion support — not reusable as-is,
though its two-tier "durable fact vs. one-off event" distinction is kept
as a conceptual design input for `category`.

## What's deliberately not here yet

No `app.py` startup/shutdown, no real audio I/O, no LLM calls, no
scheduler, no SQLite migrations, no parent-control auth. See
`docs/decisions/0001-milestone-0-scope.md` for the full list and why —
Milestone 1 needs a separate approval before any of this becomes real
code, per the spec's own instruction.
