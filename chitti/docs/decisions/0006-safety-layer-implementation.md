# 0006 — Safety layer: output screening + tool-call validation

Date: 2026-10-13
Status: Accepted

## Context

First real feature built after Milestone 1, per the agreed build order
(safety → memory → LLM backend/Finnish benchmark → conversation logic →
voice I/O once hardware exists). Chosen first because every later
conversational feature (Teachable-Friend, repeat-after-me, Story
Companion) depends on it, and it's the one piece buildable and fully
testable today without any AI backend decision or real hardware.

## What was built

- `safety/checks.py`: `check_speech(text) -> SafetyVerdict` — deterministic,
  offline (no AI call, no network): profanity via `better-profanity`
  (MIT, maintained), plus pattern-based checks for unsafe content, human
  impersonation, parent-secrecy, and engagement manipulation (same
  honest "pattern list, not real understanding" caveat as
  `pixel-ai/pixel_memory.py`'s `detect_rename_request()`/
  `detect_goodbye()`). `decline_message(verdict)` gives a gentle,
  category-matched refusal.
- `safety/tool_validation.py`: `validate_tool_call(name, arguments,
  allowed_tools) -> ToolCallVerdict` — fixed allowlist + `jsonschema`
  (MIT) validation. Never executes anything; only answers yes/no.
- 14 new unit tests (31 total passing), including a false-positive
  sanity check against classic profanity-filter substring traps
  ("Scunthorpe," "bass," "cockatoo," "classroom") and an explicit test
  proving repeat-after-me-style echo requests get the same treatment as
  any other speech.

## Explicit scope boundary

Distress/abuse-disclosure detection in a child's own speech (spec
section 5's "encourage a trusted adult... escalation response") is
**not** attempted here. This is a fundamentally different, much
higher-stakes problem than screening Chitti's own output — shipping
even a placeholder keyword detector for something this serious without
qualified child-safety/clinical input would overstate what's actually
been solved. Tracked as risk register #15, explicitly open by design.

## Consequences

- Risk register #1, #2, and #12 updated from "architecture only" to
  "mitigated in code" — with the caveat that none of this is wired into
  a real conversation loop yet, since `conversation/` doesn't exist
  until the next build step.
- New dependencies: `better-profanity`, `jsonschema` (both MIT,
  added to `pyproject.toml`).

## Not yet done

- Wiring `check_speech()`/`validate_tool_call()` into an actual
  conversation loop — waits for `conversation/` and a real
  `LanguageModelBackend` (next build steps per the agreed order).
- A real moderation-API/classifier layer as defense-in-depth alongside
  the pattern checks — flagged in `checks.py`'s docstring as needed
  before real deployment, not built this pass.
