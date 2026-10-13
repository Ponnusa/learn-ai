# Architecture — Milestone 0 proposal

Status: proposal, not yet built beyond typed interface stubs. See
`docs/decisions/0001-milestone-0-scope.md` for what this pass did and did
not implement, `docs/decisions/0002-teachable-friend-story-companion-and-parent-ui.md`
for four later pivots (teachable-friend persona, story companion,
wake-word shortlist, LAN-only parent UI), and
`docs/decisions/0003-age-config-multi-child-finnish-sequencing-teach-scope-story-source.md`
for multi-child profiles, Finnish sequencing, teach scope, and story
source — all amend sections below.

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
| F. Education Engine → **Teachable-Friend + Story Companion** (see decision 0002) | `companion_robot/education/` | 4 |
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

### Wake word (decision 0002)

Most efficient on-device wake-word engines (openWakeWord, Porcupine) need
a trained model per wake word — a child can't just say an arbitrary word
and have it recognized. The child names Chitti (and sets its wake word)
by picking from a short vetted list (5-10 names) the chosen engine
already supports well, not by training a custom model on an arbitrary
word. The parent approves/can reset the chosen name before it goes live.
Custom per-word training is a possible later upgrade, not v1 scope.

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

**Language sequencing (decision 0003):** Finnish is a committed
requirement for launch, not optional — but not required for the first
working prototype. English ships first for development velocity; Finnish
is verified and added before anything resembling a pilot, given the
target market (spec: Finland first, then EU).

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

## Teachable-Friend + Story Companion (supersedes spec section 7's first activity — decision 0002, refined in 0003)

Spec section 7 originally asked for a deterministic, in-code-validated
multiplication-practice activity. Per decision 0002, this is replaced for
the MVP by two conversational capabilities, both owned by
`conversation/` rather than a graded `education/` engine:

- **Teachable-Friend**: Chitti plays a curious peer the *child* teaches —
  grounded in the protégé effect (explaining something to a listener
  improves the explainer's own understanding). No answer key, no grading
  — there's no "activity session" with a correctness state to validate,
  so this doesn't need `education/`'s originally-planned interface at
  all. The Safety layer (see above) still screens anything Chitti echoes
  back, so an unsafe or false claim the child states isn't uncritically
  repeated. Per decision 0003: the child can teach Chitti about *any*
  topic, not just STEM-adjacent ones — the Safety layer's age-
  appropriateness and profanity/bad-language filtering has to cover
  arbitrary subject matter, not a narrow curated set.
  - **Repeat-after-me (decision 0003)**: a mode where Chitti repeats back
    what the child just said — likely a toddler-friendly language-play
    game. This is **not** a literal unfiltered echo: it passes through
    the same Safety-layer filtering as any other Chitti speech. A request
    to repeat profanity or unsafe content is gently declined (e.g. "I
    don't say that word, let's try a different one!"), never carved out
    as an exception to the safety boundary.
- **Story Companion**: Chitti narrates a story it already has a certain
  transcript for, then answers questions about it grounded *only* in
  that transcript — held as session-only conversation context (spec
  section 6 category 1), fed back to the `LanguageModelBackend` as
  grounding so answers can't drift into general world knowledge that
  might contradict the story. Per decision 0003, the transcript comes
  from either a **preloaded story library** or a **parent-uploaded
  story** (via the Parent Controls web UI, below) — not from ASR-
  transcribing a child's own out-loud reading, which would carry real
  transcription-accuracy risk. Parent-uploaded content is trusted as-is
  (format/size validated, not content-moderated) since the parent is the
  authorizing adult. No camera/OCR involved — stays within spec section
  2.2's camera exclusion.

`companion_robot/education/` is kept as a package in case a deterministic
activity (e.g. basic maths) is reintroduced later, but nothing in it is
being built against the MVP scope today.

## Child profiles (decision 0003)

Multiple children can share one physical Chitti, each with their own
profile: age/age-band (parent-configured, drives persona complexity),
memory, preferences, and story/learning history. `memory/schema.py`'s
`MemoryRecord` now carries `child_profile_id` so every record is scoped
to one child and never returned or editable across profiles.

**Switching mechanism (decision 0003)**: spec section 2.2 excludes
voice-based identity recognition of children from the MVP, so Chitti
cannot automatically tell which sibling is speaking. Resolved via an
explicit **self-ID phrase** ("Hey Chitti, it's Anna"), detected from the
transcribed speech using the same pattern-list phrase-detection technique
already proven in `pixel-ai/pixel_memory.py`'s `detect_rename_request()`
(reused as a technique, not copied as code). Chitti should audibly
confirm the switch ("Hi, Anna!") so a sibling saying the wrong name gets
caught and corrected immediately rather than silently loading the wrong
profile for a whole session — a design recommendation, not yet built.

## Memory Service (spec section 6)

`memory/` defines a versioned record type now (`MemoryRecord` dataclass:
`id`, `child_profile_id`, `category`, `content`, `created_at`,
`updated_at`, `expires_at`, `source`, `consent_or_authorization_status`,
`retention_policy`, `schema_version` — `child_profile_id` added per
decision 0003 for multi-child support) with no storage logic yet. This
supersedes
`pixel-ai/pixel_memory.py`'s flat Markdown upsert/append file, which has
no consent, retention, expiry or deletion support — not reusable as-is,
though its two-tier "durable fact vs. one-off event" distinction is kept
as a conceptual design input for `category`.

## Reminder Service: alarms (decision 0002)

Alarms are not a separate service — they're the existing `reminders/`
service (spec section 8) with an alarm-style alert (louder/sustained
audio, voice snooze/dismiss) rather than a one-shot spoken notice. Same
local-scheduler guarantee applies: the LLM is never relied on to trigger
one at the right time.

## Parent Controls: local web UI, LAN-only (decision 0002)

`parent_controls/` is a local web UI served by the robot itself — not a
cloud account or companion-app system — reusing the Flask-on-a-
background-thread pattern already proven in `pixel-ai/photo_receiver.py`.

- **Discovery**: mDNS (Avahi) advertises a `.local` hostname (e.g.
  `chitti.local`) so the parent doesn't need to know an IP address.
- **First-boot onboarding**: before the robot joins the home WiFi, it
  briefly broadcasts its own temporary setup hotspot (same pattern as
  typical smart-home devices); the parent connects once, enters home
  WiFi credentials *and* sets the parent PIN, then the hotspot goes away.
- **Auth**: PIN-gated from the very first boot (closes risk register
  #8), with rate-limited login attempts.
- **Explicitly LAN-only**: never port-forwarded or exposed to the public
  internet. Confirmed with the product owner — no remote/away-from-home
  access in this version. That would need a cloud relay or companion app,
  which is a materially bigger, more compliance-heavy build, scoped
  separately if ever wanted.
- **Child profile management (decision 0003)**: create/edit each child's
  profile (name, age/age-band, feature toggles) from this UI.
- **Story management (decision 0003)**: upload, list, and remove stories
  for the Story Companion to narrate from.

## What's deliberately not here yet

No `app.py` startup/shutdown, no real audio I/O, no LLM calls, no
scheduler, no SQLite migrations, no parent-control auth. See
`docs/decisions/0001-milestone-0-scope.md` for the full list and why —
Milestone 1 needs a separate approval before any of this becomes real
code, per the spec's own instruction.
