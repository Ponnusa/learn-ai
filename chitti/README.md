# Chitti — Companion Robot (child-safe AI companion)

Status: **Milestone 0 — assessment and scaffolding only.** No functional
code exists yet. See `docs/decisions/0001-milestone-0-scope.md` for
exactly what this pass delivered and what's deliberately not here.

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

- No hardware in hand yet (Raspberry Pi 5) — everything here is designed
  to be developed and tested without it, with hardware interfaces that
  can be mocked.
- `src/companion_robot/` has typed interface stubs for the voice
  architecture (`SpeechToSpeechBackend`, `SpeechRecognitionBackend`,
  `LanguageModelBackend`, `TextToSpeechBackend`, `AudioTransport`) and a
  typed `MemoryRecord` schema — no implementations, no running app yet.
- Every other service package (`device/`, `conversation/`, `safety/`,
  `education/`, `reminders/`, `parent_controls/`, `storage/`,
  `diagnostics/`) exists as an empty package with a docstring stating
  which milestone will fill it in.

## Documentation

Start with `docs/architecture.md` (module map + AI backend comparison),
then `docs/risk_register.md` and `docs/decisions/` for why things are
built the way they are. `docs/compliance_plan.md` and
`docs/privacy_data_map.md` track what's explicitly **not yet assessed** —
don't treat their presence as a compliance claim.

## Next step

Milestone 1 (local device foundation — spec section 12) needs a separate,
explicit approval before implementation starts, per the spec's own
instructions. See the open items in
`docs/decisions/0001-milestone-0-scope.md`.
