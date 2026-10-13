# Risk register — initial (Milestone 0)

Status: initial pass, compiled from reading `pixel-ai/` and the product
spec. Not a complete safety/security risk assessment — that's Milestone 6
with qualified external input (spec section 14). Update this file as
risks are found, mitigated, or closed; don't delete resolved rows, mark
them Closed with the mitigation and date.

| # | Risk | Source | Severity | Mitigation (planned) | Status |
|---|---|---|---|---|---|
| 1 | Safety policy enforced only via LLM system prompt, bypassable by prompt injection or model drift | `pixel-ai/pixel_teaching_prompt.py` does exactly this; spec section 5 forbids it | High | `safety/` as independent, tested application code, post-processing every model response before speech/tool-execution | Open — architecture only |
| 2 | Model-authored tool calls executed without schema validation, or a tool that lets the model run arbitrary code/commands | Spec section 9; directly discussed with the user re: pygame animation code-gen (decided against `exec()`-ing model output) | High | Fixed tool allowlist + strict JSON-schema validation in `conversation/`, enforced before `device/` or any execution path is reached | Open — architecture only |
| 3 | Education engine accepts the model's own correctness judgment instead of deterministic checking | No answer-validation exists anywhere in pixel-ai | High | `education/` owns correctness in code; model only explains/hints | Open — architecture only |
| 4 | Memory storage has no consent, retention, expiry or deletion mechanism | `pixel-ai/pixel_memory.py` is a flat upsert/append Markdown file | High | Versioned `MemoryRecord` schema (spec section 6) in SQLite from the start, with a deletion API from Milestone 3 | Open — schema stubbed only |
| 5 | TTS dependency (`gTTS`) calls an undocumented, unofficial Google endpoint with no commercial terms | Found reading `pixel-ai/pixel_tts.py` | Medium | Default to `piper-tts` (local, MIT) or a properly licensed commercial TTS; never carry gTTS into chitti | Open |
| 6 | AI backend data leaves the EU with unverified residency/retention terms | Spec section 6 ("minimise data sent to cloud providers... document whether processing occurs locally, in the EU or elsewhere") | High | Backend comparison in `architecture.md`; must be verified per-vendor before any child-facing pilot, not assumed | Open — comparison only, no verification yet |
| 7 | Finnish-language quality/latency unverified for every candidate AI backend | Spec section 4 ("do not assume a model supports Finnish... until verified") | Medium | Measurement required before Milestone 2 backend selection | Open |
| 8 | Parent-control interface has no authentication model defined yet | Spec section 9 requires auth for parent controls; nothing built yet | High | Must be designed in Milestone 1/5, not deferred informally | Open |
| 9 | Physical mute/emergency-stop could end up software-dependent if `device/` isn't built hardware-independent from the start | Spec core principle 6 and section 3.1 | High | `device/` interfaces designed now so mute/e-stop never route through the Conversation Service or any cloud call | Open — interfaces not yet written (Milestone 1) |
| 10 | No legal/compliance assessment exists (toy safety, GDPR, AI Act, RED/CRA) | Spec section 14 explicitly requires qualified external specialists | High (blocking for any pilot) | Tracked in `compliance_plan.md`; out of scope for a coding agent to resolve | Open, by design — not this project's job to close |
| 11 | Vendor child-directed-use policies (OpenAI, Anthropic) not checked for this specific use case | Spec section 2.2/5 context; not yet researched | Medium | Must check both vendors' usage policies for apps directed at children under 12 before committing to either | Open |

## Review cadence

Revisit this register at the start of every milestone, and immediately
after any finding from `/code-review` or `/security-review` that touches
safety, memory, or tool-calling code.
