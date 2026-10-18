# 0004 — Modular ASR+LLM+TTS pipeline chosen over OpenAI Realtime for the MVP

Date: 2026-10-13
Status: Accepted
Reverses: `architecture.md`'s original recommendation ("prototype behind
`SpeechToSpeechBackend` with OpenAI Realtime first for engineering
velocity").

## Context

Discussed OpenAI Realtime's suitability for Chitti specifically (not
just in general). It's the strongest option for conversational quality —
`pixel-ai/pixel_openai_voice_semantic.py` already proves out its
barge-in, low-latency streaming, and tool-calling. But a structural
tension with spec section 5 surfaced: Realtime is audio-native, so
speech starts streaming out as it's generated, without a reliable
text-first checkpoint. Spec section 5 requires safety to be "enforced in
application logic... after every model response, before it's spoken" —
a modular ASR→LLM→TTS pipeline gives exactly that checkpoint (validate
the model's text, then and only then synthesize approved speech);
Realtime does not, without added moderation-buffering complexity.

## Decision

Build the MVP on a **modular pipeline**, not `SpeechToSpeechBackend`/
Realtime:

- **TTS**: `piper-tts` — already evaluated in `pixel-ai/pixel_tts_piper.py`,
  MIT, fully local. Avoids the `gTTS` problem (risk register #5)
  regardless of which LLM is chosen.
- **ASR**: `faster-whisper` — already proven in
  `pixel-ai/local_stt_server.py`. That same evidence is a reason to
  benchmark, not assume: that server runs on a separate "fast machine,"
  not the Pi itself, so whether Pi 5 alone is fast enough for real-time
  transcription here is unverified, not assumed either way.
- **LLM**: kept genuinely provider-neutral via the already-built
  `LanguageModelBackend` interface. OpenAI's and Claude's text models
  should be benchmarked side-by-side specifically on **Finnish quality**
  before either is committed to, since Finnish is a committed launch
  requirement (decision 0003) and nothing has tested it yet.

**What this does not cost**: barge-in/interrupt latency (spec's <200ms
target) is primarily a local playback-cancellation property — the same
mechanism as `pixel-ai/pixel_tts.py`'s `stop()` terminating the audio
process — not a function of which backend generates speech. Going
modular doesn't hurt this.

**What this does cost**: first-response latency. Three sequential hops
(transcribe → generate → synthesize) will be slower than Realtime's
single streaming hop; the spec's "~1 second first response" target gets
harder to hit. Must be measured once real hardware exists, not assumed.
If it proves unacceptably slow, Realtime (with an added moderation-
buffer mitigation to partially close the safety-checkpoint gap) becomes
the fallback to revisit — not the default to start from.

## Consequences for existing docs

- `architecture.md`'s "AI backend comparison" section and its
  recommendation updated to reflect this decision.
- Risk register items #6 (EU residency), #7 (Finnish), #11 (vendor
  child-directed-use policy) all stay open, now scoped to whichever text
  LLM is eventually chosen rather than to Realtime specifically — the
  underlying verification work doesn't go away just because the backend
  shape changed.

## Open follow-ups

- Benchmark `faster-whisper` on Pi 5 alone (once hardware exists) before
  assuming it needs a separate machine the way `pixel-ai`'s does.
- Benchmark OpenAI vs. Claude text models on Finnish quality before
  picking one.
- Measure actual first-response latency on the real pipeline before
  deciding whether it meets the spec's ~1s target or needs revisiting.
- **2026-10-18, flagged by external feedback on Reading Partner's
  teleprompter (decision 0053)**: a genuinely reactive word-highlight
  (advancing only when the child's word is actually recognized,
  rather than decision 0053's timer-paced highlight) needs streaming/
  partial speech recognition, which this decision's modular pipeline
  doesn't have -- `audio/real.py` is push-to-talk only (documented
  there), and `voice/stt_openai.py` only exposes one-shot batch
  transcription. Worth a dedicated feasibility evaluation before
  committing to it, not a quick add-on to Reading Partner alone: a
  streaming *input* backend doesn't reopen this decision's actual
  safety-checkpoint concern (that was about Chitti's own *output*
  speech skipping text-level screening), but it's still a new backend
  with its own cost/latency/privacy profile, and would need
  `audio/real.py`'s capture model and `device/screen_face.py`'s
  render loop both extended to consume live partial results instead
  of a timer. Not started.
