# Security threat model — initial (Milestone 0)

Status: lightweight first pass (STRIDE-style), scoped to what's known at
Milestone 0. Revisit and deepen at Milestone 6 (spec section 14) with
qualified input; this is not a substitute for that.

| Category | Threat | Mitigation (planned) |
|---|---|---|
| Spoofing | Parent-control interface reachable by anyone on the home WiFi | PIN set during first-boot setup-hotspot onboarding, rate-limited login, discovered via mDNS (`chitti.local`), never port-forwarded or exposed beyond the LAN (decision 0002) |
| Tampering | Model-authored tool-call arguments used without validation | Strict JSON-schema validation per tool, fixed allowlist, enforced in `conversation/` before any handler runs (spec section 9) |
| Tampering | Model instructed to produce or the app asked to run arbitrary code (e.g. an LLM-generated pygame script) | Never implement a "run this code" tool; every visual/behavior capability is a fixed, pre-written function with typed, validated arguments — same reasoning already given to the user for the earlier pygame-animation question |
| Repudiation | Logs capturing raw audio or unnecessary personal data by default | Structured logging excludes raw audio and PII by default (spec section 2.1); any opt-in audio logging is explicit and clearly flagged, mirroring `pixel-ai`'s existing `PIXEL_AUDIO_LOG_DIR` opt-in pattern |
| Information disclosure | Secrets (API keys) committed to source control or leaking into logs | `config/` fails fast on a missing required secret (same `_require()` pattern as `pixel-ai/config.py`), `.env` gitignored, no secret ever logged |
| Information disclosure | Cloud AI backend receives more data than necessary, or data leaves the EU without being documented | Minimise what's sent per-turn; document every external service + data recipient in `privacy_data_map.md`; verify vendor residency terms before any pilot (risk register #6) |
| Denial of service | External API calls (LLM, ASR, TTS) with no timeout/rate limit | Every outbound call wrapped with a timeout and sane retry/backoff; graceful degradation to offline mode on repeated failure (spec section 9) |
| Elevation of privilege | AI-generated text or tool call reaching motor control, GPIO, or emergency-stop | `device/` physically isolates these from `conversation/` — no code path connects them; this is an architectural invariant, not a runtime check |
| Elevation of privilege | A compromised or malicious dependency gaining filesystem/network access beyond what's needed | Dependency pinning + licence/provenance review (`model_and_licence_inventory.md`); least-privilege service account once deployed (spec section 9) |

## Known gaps at Milestone 0

- No penetration testing, no vulnerability scanning tooling wired up yet.
- No signed-update mechanism designed yet (needed before any commercial
  deployment, spec section 9).
- Parent web UI (decision 0002) has a PIN-auth *plan* but no session/
  CSRF design yet, and no TLS plan for the LAN connection -- a real
  certificate for a `.local` hostname isn't straightforward (self-signed
  would warn in every browser). For now this would run as plain HTTP on
  a trusted home LAN, same posture `pixel-ai/local_stt_server.py`
  already takes for a lower-stakes endpoint -- worth deciding explicitly
  once this is actually built, not inheriting that posture by default
  given parent-control data is more sensitive.
- Network allowlisting for service-to-service calls not yet designed —
  there's only one service today (the Pi itself); revisit once any
  separate "fast machine" or cloud component is introduced (echoes
  `pixel-ai`'s own local_stt_server.py design, which is explicitly
  documented there as LAN-only, no auth, "fine on a trusted home
  network" — that exact posture would need re-justifying for chitti, not
  assumed acceptable).
