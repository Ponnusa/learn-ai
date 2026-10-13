# Dependency and model licence inventory — Milestone 0

Status: covers what's referenced by the Milestone 0 skeleton and the
candidates evaluated for Milestone 1+. Not yet a full SBOM (spec section
3.2.I asks for one as the project matures) — this is the starting review.

## In the Milestone 0 skeleton today

| Dependency | Licence | Use | Notes |
|---|---|---|---|
| Python stdlib | PSF | Everything | — |
| SQLite (via stdlib `sqlite3`) | Public domain | Planned local store (Milestone 3+) | Not wired up yet, schema only |
| pytest | MIT | Testing | Not yet added to `pyproject.toml` — add when Milestone 1 introduces real tests |

## Candidates evaluated, not yet chosen

| Dependency | Licence | Role | Evaluated via |
|---|---|---|---|
| `piper-tts` | MIT | Local TTS | Already evaluated in `pixel-ai/pixel_tts_piper.py` — runs fully offline, no cloud dependency. Default recommendation over `gTTS` (see below) |
| `faster-whisper` (+ CTranslate2) | MIT | Local ASR candidate | Already in production use in `pixel-ai/local_stt_server.py`, including a documented PyAV version-compatibility workaround worth reusing as a lesson, not code |
| `webrtcvad` | BSD-3-Clause | VAD candidate | Not yet benchmarked for chitti |
| `openwakeword` | Apache-2.0 | Wake-word candidate (decision 0002's shortlist approach) | Fully open, no per-use licensing cost — preferred over Porcupine for that reason; not yet benchmarked for chitti |
| Picovoice Porcupine | Commercial (free tier + paid tiers) | Wake-word alternative, not currently planned | Requires an account/API key and has usage limits on its free tier — a real cost/licensing consideration if ever chosen instead of openWakeWord; noted here so it isn't picked without that being seen |
| Flask | BSD-3-Clause | Parent-controls local web UI (decision 0002) | Same library already used in `pixel-ai/photo_receiver.py` — same Flask-on-a-background-thread pattern, not yet added to chitti's own dependencies |
| `zeroconf` (or system Avahi) | LGPL-2.1 (`zeroconf` package) / GPL (Avahi itself, used via its daemon, not linked) | mDNS advertisement for `chitti.local` discovery (decision 0002) | Not yet benchmarked for chitti; Avahi is typically already present on Raspberry Pi OS as a system service, not a Python dependency to vet the same way |
| `pydantic` | MIT | Config validation | Not yet added |
| OpenAI Python SDK | Apache-2.0 | `SpeechToSpeechBackend`/`LanguageModelBackend` candidate | SDK licence only — **OpenAI's commercial API usage terms for a child-directed product have not been checked** (risk register #11) |
| Anthropic Python SDK | MIT | `LanguageModelBackend` candidate | SDK licence only — **Anthropic's usage policies for a child-directed product have not been checked** (risk register #11) |

## Explicitly evaluated and rejected

| Dependency | Licence | Why rejected for chitti |
|---|---|---|
| `gTTS` | MIT (library itself) | Calls an undocumented, unofficial Google Translate TTS endpoint with no commercial terms or SLA. Fine for `pixel-ai`'s current non-commercial educational prototype; not appropriate for a commercial child-facing product (spec section 9: "prefer maintained libraries with suitable licences"). Found reading `pixel-ai/pixel_tts.py`. |

## Model provenance (spec section 1, core principle 9)

Not yet applicable — no AI model has been selected for chitti (see
`architecture.md`'s backend comparison). Once one is chosen, record here:
model name/version, provider, licence or usage terms, and whether any
fine-tuning or training on this product's data occurs (spec section 6
default: no).

## Maintenance

Re-run a dependency/licence check whenever `pyproject.toml` changes, and
before every milestone's acceptance review (spec section 13: "third-party
dependency and model licences are documented").
