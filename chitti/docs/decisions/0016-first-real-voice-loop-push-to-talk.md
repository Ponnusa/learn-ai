# 0016 — First real voice loop: push-to-talk, OpenAI STT/TTS, live memory

Date: 2026-10-13
Status: Accepted

## Context

Product owner asked for a real, end-to-end test on the Pi 1 B+: real
audio in/out, Teachable-Friend/Story Companion conversation, memory
building live, visible in Parent Controls — "like pixel-ai."

## Wake-word investigation (resolved: not viable on this chip, for now)

Checked before building anything, rather than guessing:
- **openWakeWord**: depends on `onnxruntime` or `tflite-runtime` for
  inference. Checked PyPI's actual published wheels directly —
  `onnxruntime` ships only `aarch64`/`x86_64`, `tflite-runtime` ships
  only `armv7l`/`aarch64`. **Neither publishes an ARMv6 wheel**, and
  the Pi 1 B+'s ARM1176JZF-S core is ARMv6 at the hardware level, so no
  OS choice routes around this. Confirmed dead end on this device.
- **Porcupine**: ships a pure-Python wheel (native binaries bundled/
  fetched internally, not gated by PyPI arch tags). Picovoice's own
  docs list "Raspberry Pi (Zero, 3, 4, 5)" as supported, but describe
  architecture support as "Arm Cortex-A"/"Arm Cortex-M" — the Pi 1 B+'s
  ARM1176JZF-S is an ARM11 core, predating Cortex-A. Genuinely
  ambiguous from documentation alone; would need a direct hardware
  test with a real (free-tier) AccessKey to resolve, not more reading.

**Decision**: push-to-talk via keyboard Enter for this device, since it
has no physical button. Wake-word stays the real goal for Pi 5, where
`aarch64` wheels make openWakeWord straightforwardly viable.

## What was built

- `audio/real.py`: `RealAudioTransport` — real `play()`/`stop_playback()`
  via `aplay`, same subprocess pattern (`stdin=DEVNULL`,
  `start_new_session=True`) already proven in `pixel-ai/pixel_tts.py`.
  `capture_chunks()` deliberately raises `NotImplementedError` — true
  continuous streaming capture is real Milestone 2 scope once wake-
  word/VAD exists; this transport pairs with `voice_loop_demo.py`'s own
  bounded-clip recording instead.
- `voice/stt_openai.py`: `OpenAIWhisperBackend` — real
  `SpeechRecognitionBackend` implementation (`whisper-1`).
- `voice/tts_openai.py`: `OpenAITTSBackend` — real
  `TextToSpeechBackend` implementation, requesting `response_format:
  "wav"` directly so playback needs no mp3 decoder.
- `voice_loop_demo.py`: the actual push-to-talk loop. Two modes:
  Teachable-Friend (records a clip, transcribes, runs
  `ConversationService.teachable_friend_reply()`, speaks the reply,
  writes a `LEARNING_STATE` memory record) and Story Companion (reads
  a story from the same `StoryRepository` the Parent Controls UI
  manages, then takes questions grounded in it). Both write to
  **the same `chitti/data/chitti.db`** `parent_controls/app.py` uses,
  so the parent-facing UI reflects new memories live, no extra wiring
  needed.
- Decision 0003's open question — "does Teachable-Friend content ever
  become durable memory?" — is answered concretely for this demo: yes,
  logged as `LEARNING_STATE`, tagged `retention_policy="demo"` so it's
  identifiable as demo data, not a final product policy.
- 4 new unit tests (85 total passing) against mocked HTTP for both new
  backends — request shape and missing-API-key fail-fast, same pattern
  as the existing OpenAI/Claude `LanguageModelBackend` tests.

## Explicitly not run — needs the real Pi

`arecord`/`aplay` and real mic/speaker hardware don't exist in this
agent's dev sandbox. `RealAudioTransport` is confirmed instantiable
(no missing abstract methods) and the module compiles, but the actual
push-to-talk loop has only been verified this far, not run end to end.
That's the next step, on the Pi.

## Known rough edges, stated rather than hidden

- Fixed 16kHz mono capture, no silence trimming — a very short or very
  long press will still get sent to Whisper as-is.
- No barge-in during playback for this demo (keyboard is busy waiting
  for the next Enter press, not watching for interrupt input mid-reply).
- `is_muted()` always returns `False` — no physical mute switch exists
  on this device.

## Addendum: device override, caught by the product owner's own question

The first version hardcoded ALSA's `"default"` device for both
`arecord` and `aplay`, with no override. The product owner pointed out
`pixel-ai` already defines `PIXEL_MIC_DEVICE`/`PIXEL_SPEAKER_DEVICE`
for exactly this — its own README documents real-hardware experience
that `"default"` often doesn't route to the actual USB mic/speaker on
this chip, and every one of its voice scripts passes the device
explicitly via `-D`. Same constraint applies here, so `audio/real.py`
now exposes `CHITTI_MIC_DEVICE`/`CHITTI_SPEAKER_DEVICE` (chitti's own
env var names, not pixel-ai's — the two projects' configs stay
independent per decision 0001, even though it's the same physical
device and likely the same value). `voice_loop_demo.py`'s capture
helper imports the same `CAPTURE_DEVICE` constant rather than
duplicating the env-var read.

## Addendum 2: the device override didn't actually work on real hardware — same `load_dotenv()` bug class, again

Live on the Pi, with `CHITTI_MIC_DEVICE=plughw:2,0` correctly set in
`.env`, the real run still transcribed near-silence as "you" (Whisper's
classic hallucination for near-empty audio). Diagnosed step by step on
real hardware rather than guessed at: `arecord -D plughw:2,0 -f S16_LE
-r 16000 -c 1 -d 5 test.wav` manually, played back with `aplay`,
confirmed real speech was captured correctly and the mic's ALSA
capture gain was on at 79% — the hardware path itself was fine.

The actual bug: `audio/real.py` reads `CHITTI_MIC_DEVICE`/
`CHITTI_SPEAKER_DEVICE` from `os.environ` **at module import time**
(`CAPTURE_DEVICE = os.environ.get(...)`), and `voice_loop_demo.py`
imports `audio.real` as its *first* import — before anything that
would otherwise trigger `config/loader.py`'s `load_dotenv()` call.
`.env` hadn't been loaded yet, so both constants silently fell back to
ALSA's `"default"` device regardless of what `.env` said. This is the
exact same bug class already hit once in `pixel-ai`
(`pixel_direct_llm.py` reading `os.environ` directly before anything
had loaded `.env`) and explicitly guarded against when
`config/loader.py` was built for chitti (decision 0008) — but that
guard only protects callers that actually import `config.loader`
first; it doesn't protect a new file that reads `os.environ` directly
without importing it at all.

**Fix**: `audio/real.py` now imports `companion_robot.config.loader`
(triggering its `load_dotenv()`) before reading either env var, making
it self-sufficient regardless of import order elsewhere. Confirmed via
a standalone repro: importing `audio.real` as the very first import in
a fresh process, with only `.env` (no shell-level env var set), now
correctly resolves `CHITTI_MIC_DEVICE` instead of silently defaulting.

Checked whether this pattern recurs elsewhere:
`grep -rn "^[A-Z_]+ = os\.environ\.get"` across `src/` found exactly
one match — this file. Every other backend
(`openai_backend.py`/`claude_backend.py`/`stt_openai.py`/
`tts_openai.py`) reads its env vars lazily inside an async method via
`require_env()`, not at import time, so none of them were exposed to
this.

## Addendum 3: first full real-hardware success, and a discoverability gap

With both fixes above applied, the product owner ran a real
Teachable-Friend session end to end on the Pi: real speech → Whisper
→ `ConversationService` → spoken reply → a `LEARNING_STATE` memory
record per exchange. The persona held up well against a real model —
asked genuine follow-up questions, stayed in the curious-peer role for
most of the conversation (with one natural but notable exception: it
briefly posed its own addition question and graded the child's answer
to it, a minor persona drift worth knowing about, not a safety issue).

The memory records were confirmed present via `curl`/browser at
`/profiles/demo-child/memories` directly, but **absent from the normal
`/profiles` page** — nothing had ever created a `ChildProfile` row for
`demo-child`, so Parent Controls had no profile row to link to, even
though the data was really there. A parent using the UI as designed
(click through from the profile list) would never have found it.

**Fix**: `voice_loop_demo.py`'s `main()` now ensures a `ChildProfile`
row exists for `demo-child` (name "Demo Child", age 7) before the
conversation loop starts, via the same `ChildProfileRepository`
`parent_controls/app.py` uses. Idempotent — checked via a standalone
repro running the ensure-logic twice against one connection, confirming
no duplicate profile is created on a second run of the demo.
