# 0001 — Milestone 0 scope and four structural decisions

Date: 2026-10-13
Status: Accepted

## Context

The project owner handed over the full "Companion Robot" (codename
Chitti) product specification (`docs/product_spec.md`) and asked for a
brainstorm, a plan, and clarifying questions where needed. The spec
itself mandates a Milestone 0 (inspect, document, list open decisions,
wait for approval before any Milestone 1 implementation) before any real
code is written.

## Decisions

1. **Repository location**: new folder in the existing `learnai` repo,
   at `learnai/chitti/` — not a separate standalone repository.
   Trade-off accepted: this mixes a commercial child-safety product's
   compliance docs/SBOM/licence register into the same repo history as
   the LearnX teaching platform and Pixel AI. Revisit if/when chitti's
   compliance or release lifecycle needs genuine separation (e.g. a
   different legal entity, a different access-control boundary for the
   compliance docs).

2. **Hardware status**: no Raspberry Pi 5 is in hand yet. This is a
   software-only prototype for now. Every hardware-facing interface
   (`device/`, `audio/`) is designed to be mockable/stubbable from day
   one — the same posture `pixel-ai/pixel_face.py` eventually needed for
   its SDL-driver fallback, but applied from the start here rather than
   discovered after the fact.

3. **Reuse approach**: `pixel-ai/` is a **design reference only**. No
   files are copied into chitti. Rationale: pixel-ai was not built under
   chitti's constraints (no consent-tracked memory, no deterministic
   answer-checking, safety logic lives in prompt text, direct coupling to
   the LearnX backend) — copying code would carry those gaps in silently.
   Patterns worth keeping are described in prose in `architecture.md` and
   re-implemented from the spec's requirements, not copy-pasted.

4. **AI backend**: left undecided. A comparison (OpenAI Realtime vs. a
   Claude-based ASR+LLM+TTS pipeline vs. a local/Moshi-style stack) is
   recorded in `architecture.md`, with a recommendation to prototype
   behind a provider-neutral interface using OpenAI Realtime first for
   engineering velocity — but the actual choice needs Finnish-language
   measurement and both vendors' child-directed-use policies checked
   first, neither of which has been done.

## Milestone 0 scope (what this pass built)

Per the spec's own Milestone 0 deliverable list: existing-code inventory,
architecture proposal, hardware assumptions, dependency/licence review,
initial threat model, initial risk register, and this decision log — plus
a **behavior-free** skeleton: directory structure for every spec-section-
3.2 service, and five typed interface stubs (`SpeechToSpeechBackend`,
`SpeechRecognitionBackend`, `LanguageModelBackend`, `TextToSpeechBackend`,
`AudioTransport`) plus a typed `MemoryRecord` dataclass — all with
`NotImplementedError` bodies, no real logic.

**Explicitly not built**: `app.py` startup/shutdown, real microphone/
speaker code, any real LLM call, the education engine's answer-checking,
the reminder scheduler, parent-control auth, SQLite migrations. These are
Milestone 1+ and need a separate, explicit approval before implementation
starts, per the spec's instruction #20 and its "first task" section.

## Open items carried forward (listed back to the project owner)

1. Final AI backend choice — blocked on Finnish-language measurement.
2. Wake-word vs. push-to-talk-only for the first prototype.
3. Confirm the Python package name `companion_robot` under the `chitti`
   project folder (codename stays the folder/display name).
4. Who performs the actual legal/compliance assessment (spec section 14)
   — the spec requires qualified external specialists, not a coding
   agent, for this.
