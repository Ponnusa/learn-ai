# Pixel AI

An AI desk-companion robot for students — a peer learning friend, not a
tutor. Built by nordX Labs Oy (Helsinki), connects to the LearnX AI
platform (learnx-ai.com, this repo's `backend/`).

## Phase 1 (current): Raspberry Pi 1 B+, keyboard input, HDMI face

Hardware: Pi 1 B+, 700MHz ARMv6, 512MB RAM, Pi OS Legacy Lite 32-bit,
Python 3.11.2, ethernet, HDMI out, 3.5mm audio out. No mic/speaker/display
hardware is connected yet, so this phase uses a keyboard and an HDMI
pygame window instead.

### Prerequisite: a LearnX developer account + approved API key

`LEARNX_API_URL` must point at the backend directly
(`https://learn-ai-production.up.railway.app`) — `learnx-ai.com` is only
the Vercel-hosted frontend and 307-redirects `/api/...` calls, it never
reaches the FastAPI backend.

One call to `POST /api/developer/signup` (email, password, company_name,
description) creates both a real `users` row — its `user.id` is what
`LEARNX_USER_ID` must be, since `/api/chat/send` does a foreign-key
insert against `users(id)` and rejects an arbitrary string — and an
`lx_live_...` key in `api_key.api_key` (shown once, save it immediately).
The key comes back `status: "pending"`; `/api/public/v1/videos/...`
rejects anything not `approved`, so a super-admin has to flip it (either
`POST /api/admin/developer-keys/{key_id}/approve` with a super-admin JWT,
or `UPDATE api_keys SET status='approved', approved_at=NOW() WHERE id=...`
directly against the DB). `/api/chat/send` and `/api/uploads` don't need
the API key at all, just the `user_id`.

### Setup on the Pi

```bash
cd pixel-ai
source /home/pi/pixel_env/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in LEARNX_API_KEY and LEARNX_USER_ID
python pixel_main.py
```

**Getting the face to actually show up on an HDMI display (TV or the
eventual LCD) on a fresh Pi OS Lite image took three separate real
fixes, found on actual hardware, in this order** — worth doing all
three on a fresh SD card before assuming the face is broken:
1. **Display not detected at boot**: if `cat /proc/fb` is empty and
   `dmesg` shows `[drm] Cannot find any crtc or sizes`, the Pi booted
   before it saw the TV as connected. Add `hdmi_force_hotplug=1` to
   `/boot/firmware/config.txt`, make sure the TV is on and already on
   the right input *before* powering the Pi on, then `sudo reboot`.
2. **Missing Mesa EGL/GBM libraries**: Pi OS **Lite** has no
   desktop/X11/Wayland stack, so the Mesa userspace libraries SDL2's
   `kmsdrm` driver needs (even for plain 2D — KMSDRM fundamentally
   renders through GBM+EGL) aren't installed by default. Symptom:
   `pygame.error: EGL not initialized`. Fix: `sudo apt install -y
   libgbm1 libegl1 libgles2 libgl1-mesa-dri`.
3. **Confirmed `fbdev` is a dead end on this pygame build**: pip's
   `pygame` wheel wasn't compiled with fbdev support at all
   (`pygame.error: fbdev not available`, unconditionally, regardless of
   the above fixes) — `kmsdrm` is the one that actually works on
   current Pi OS (Bookworm+), which is why it's first in
   `pixel_face.py`'s driver fallback list.

To isolate the display path from everything else (no mic/API key
needed), test it standalone:
```bash
python3 -c "
from pixel_face import face
import time
face.start()
time.sleep(30)
face.stop()
"
```
`kmsdrm` was observed returning a `640x480` surface regardless of the
`480x320` requested in `pixel_face.py`'s `set_mode()` call — it seems
to hand back whatever mode it actually negotiated with the display,
not the requested size. `PixelFace`'s drawing math assumes the
requested size, so the face may render small/off-center rather than
centered until that's reconciled against the real returned surface
size.

### What works today

- Type a question -> `POST /api/chat/send` -> the full reply is printed,
  then spoken via `GET /api/chat/messages/{id}/audio` (the same endpoint
  the LearnX web app's "read aloud" button uses — it runs the message
  through GPT-4o-mini first to strip LaTeX/markdown into natural spoken
  prose, so Pixel doesn't read out literal asterisks and dollar signs the
  way raw gTTS on markdown text would). Falls back to gTTS on the raw
  reply only if that call fails. Face animates
  (idle/listening/thinking/talking/happy) on the HDMI window.
- `video: <word problem>` -> `POST /api/public/v1/videos/generate`, polls
  `GET /api/public/v1/videos/{id}` (~60s), prints the resulting URL. No
  local video player is wired up yet — that's a later phase.
- A photo can be POSTed to `http://<pi-ip>:5005/photo` (multipart field
  `photo`, optional `question`) — forwards to `/api/uploads` then
  `/api/chat/send` with `image_url` set, speaks the reply back.
- `game: <topic>` reports that game generation isn't available — the
  LearnX backend has no game-code-generation endpoint today. Would need
  new backend work, not just a new client.

### Ladder mode: short one-to-one guided-discovery conversations

`pixel_ladder.py` is a separate standalone script — it only imports
`pixel_face`/`pixel_tts`/`pixel_listen`/`pixel_brain`, never edits them,
so it can be run independently of `pixel_main.py`:

```bash
python pixel_ladder.py
```

Type a topic; Pixel will ask a guiding question and wait for your typed
answer instead of dumping a full explanation, continuing the exchange for
as many turns as the backend's own teaching logic decides (2-12 is
typical, fully open-ended, no cap on the backend side). This isn't new
backend behavior — `POST /api/chat/send` already decides per-reply
whether to ask a guiding question (`ladder_depth > 0`) or answer directly,
the same mechanism behind the web app's ladder-rail widget. The only
client-side requirement is reusing the same `conversation_id` across
turns, which `pixel_brain.ask()` already supports. Say "stop", "skip", or
"just tell me" at any prompt to bail out to a direct answer, mirroring
the backend's own documented shortcut phrase.

### Gemini Live mode: parked, not recommended (see voice mode instead)

**Status: parked after extensive testing.** Live sessions reliably
produced exactly one good reply, then permanent silence until an idle
timeout forced a reconnect — reproduced identically across two different
models (`gemini-2.5-flash-native-audio-latest` and `gemini-3.8-live`),
with conclusive proof via a corrected heartbeat log (`mic: N read, M
actually sent, K muted`) that audio was continuously and successfully
reaching the server for 30+ seconds with zero response. That rules out
every client-side theory tried (device-busy reconnects, a blocking
playback write, VAD tuning, muting for echo) — this is a server-side
session-handling issue with the Live API's automatic activity detection,
not fixable from this codebase. **Use `pixel_gemini_voice.py` instead**
(next section) — same persona, same persistent memory, but turn-based
over the regular `generateContent` API instead of a Live session, and it
actually works. Kept here for reference/history, not as something to
build on.

`pixel_gemini.py` is another standalone script, same non-interfering
approach — it doesn't import `config.py` at all (LearnX is paused for
this module entirely, by request), only `pixel_face` for shared states.

```bash
python pixel_gemini.py
```

Uses the Gemini **Live API** for real-time, bidirectional voice — you
talk through a USB mic (a headset or a webcam's built-in mic both work,
anything that shows up in `arecord -l`), Pixel talks back, and
turn-taking/interruption are handled by the API itself rather than
custom threading (the race-condition barge-in logic in
`pixel_discussion.py` doesn't apply here). The Live session can close on
its own (idle timeout, server-side hiccup) — `run()` reconnects
automatically when that happens rather than dying silently, logging the
real exception each time so the actual cause is visible if it keeps
recurring. Audio is captured/played via `arecord`/`aplay` subprocess, not
PyAudio — same reasoning `pixel_tts.py` already used shelling out to
`mpg123` instead of a Python audio library: avoids native bindings
(PortAudio) on this ARM hardware.

**Before running, check:**
1. **Mic hardware**: the Pi's own 3.5mm jack is output-only — you need a
   USB headset (confirmed working for this). Run `arecord -l` to find its
   card/device, then sanity-test the hardware path with no Python
   involved at all: `arecord -D plughw:<card>,<dev> -f S16_LE -r 16000 -c 1 -d 5 test.wav && aplay test.wav`.
   If that round-trip doesn't work, nothing above it will either.
2. **`pip install google-genai`** on the Pi — its core deps are `httpx`,
   `pydantic`, `websockets`, `anyio`, `tenacity`, `google-auth` (no
   `grpcio`, which is what sank the Azure SDK on this chip), and it's
   listed on piwheels.org, so it's a much better ARMv6 bet than Azure's
   SDK was — but still worth confirming it actually installs before
   relying on it.
3. **Key type**: a Google AI Studio key (`genai.Client(api_key=...)`,
   what this script assumes) vs. a Vertex AI key need different client
   setup — confirm which kind `GEMINI_API_KEY` is.
4. **Model name**: default is `gemini-2.5-flash-native-audio-latest`,
   confirmed live-capable on the real key via
   `GET /v1beta/models?key=...&pageSize=1000`, filtered for
   `bidiGenerateContent` in `supportedGenerationMethods` — not guessed.
   Other options that showed up the same way:
   `gemini-3.1-flash-live-preview`, `gemini-3.8-live` (newest generation),
   `gemini-3.8-live-extended-thinking`. These shift over time — re-run
   that same query against your own key if the default ever 404s, rather
   than guessing from docs (the model name in the original Live API docs,
   `gemini-live-2.5-flash-native-audio`, didn't exist on this key at all).
5. Set `PIXEL_MIC_DEVICE` (e.g. `plughw:1,0`, from step 1's `arecord -l`)
   if `default` doesn't route to the USB headset.

Env vars used: `GEMINI_API_KEY` (required), `GEMINI_LIVE_MODEL`,
`PIXEL_MIC_DEVICE` — set in `.env`, loaded the same way `config.py` loads
LearnX's variables, just a separate set.

### Gemini voice mode: real mic input, no Live API (recommended)

`pixel_gemini_voice.py` is the actually-working replacement for Live
voice. Same non-interfering pattern, no `config.py` import, LearnX
paused:

```bash
python pixel_gemini_voice.py
```

No persistent streaming session, no server-side voice activity
detection — turn-based, built entirely from pieces already proven
reliable: `arecord` for capture (continuously drained by a background
task so it never blocks, regardless of what the rest of the loop is
doing), simple **local** silence detection (stdlib `audioop.rms` — no
new dependency) to decide when you've finished one utterance, and the
recorded clip sent as a WAV `Part` to the exact same chat session
`pixel_gemini_text.py` uses (`client.chats.create()`/`chat.send_message()`
with a `[Part.from_bytes(data=wav_bytes, mime_type="audio/wav")]`
message) — same persona, same persistent memory via `pixel_memory.py`.
Replies are spoken via `pixel_tts`'s async primitives, with mic
forwarding muted while Pixel is talking (same no-AEC reasoning as
`pixel_gemini.py`'s mute, now proven to actually matter here too).

**Before running, check** (same as `pixel_gemini.py`'s checklist):
`arecord -l` for your mic's card/device, a raw `arecord`/`aplay`
round-trip test, and `PIXEL_MIC_DEVICE` set if `default` doesn't route
to it.

Three VAD knobs if it's too trigger-happy or too insensitive for your
specific mic/room — ambient noise floor and real speech level both vary
a lot by hardware. 300 was too sensitive on a webcam mic, triggering on
background noise and flooding the conversation with nonsense exchanges
("I can hear you rustling around over there!"). Watch the "ambient
level: current=X peak=Y" log line while it's waiting for speech — that's
real data from your actual setup, not a guess:
- `PIXEL_VAD_START_RMS` (default `600`) — loudness threshold to start
  recording.
- `PIXEL_VAD_SILENCE_MS` (default `800`) — how long a pause has to be
  before an utterance is considered finished.
- `PIXEL_VAD_MIN_MS` (default `600`) — utterances shorter than this are
  discarded before ever reaching Gemini (a noise blip that briefly
  crossed the threshold, not real speech).

Also logs each utterance's captured duration right before sending it —
useful for telling apart "two sentences got merged because the pause
between them was too short" from "captured cleanly but the model stayed
anchored to a previous topic," which look identical from the reply text
alone.

Verified the WAV encoding and the full start/stop/mute state machine
with synthetic audio (silence, "loud" samples, genuine concurrent
interleaving for the mute case) before shipping — see commit history for
the test transcripts.

Env vars: `GEMINI_API_KEY` (required), `GEMINI_TEXT_MODEL` (default
`gemini-3.8-flash`), `PIXEL_MIC_DEVICE`, `PIXEL_VAD_START_RMS`,
`PIXEL_VAD_SILENCE_MS`, `PIXEL_VAD_MIN_MS`.

### OpenAI voice mode: same local VAD, persistent streaming connection

`pixel_openai_voice.py` is a third transport option, separate provider
from everything else (LearnX paused, doesn't touch Gemini at all):

```bash
python pixel_openai_voice.py
```

Uses OpenAI's **Realtime API** — a persistent streaming WebSocket, like
Gemini Live, but deliberately with its server-side turn detection
disabled (`turn_detection: null`) in favor of the exact same local
silence-detection state machine `pixel_gemini_voice.py` already proved
reliable. After watching Gemini's server-side VAD silently break after
one turn, this doesn't trust a second provider's server VAD blind
either — local control, just over a lower-latency persistent connection
instead of one-shot `generateContent` calls per utterance.

**Everything below was verified live against the real API with a
working key before this file was written** — not guessed from docs,
which kept surfacing a stale/conflicting Beta vs GA split with different
event names:
- No `OpenAI-Beta` header needed — confirmed this account speaks the
  current (GA) wire format, with event names like
  `response.output_audio.delta` / `response.output_audio_transcript.delta`
  (not the older beta `response.audio.delta` / `response.text.delta`).
- `session.update` requires an explicit `"type": "realtime"` field and a
  nested `session.audio.input/output.format` structure. **Input rate
  must be ≥24000** — confirmed via a real `"integer below minimum
  value"` error when 16000 was tried. Unlike Gemini's asymmetric
  16kHz-in/24kHz-out, this API wants 24kHz for both directions.
- The manual-turn flow (`input_audio_buffer.append` → `.commit` →
  `response.create`) was tested end-to-end with synthetic audio through
  the actual `_record_and_stream_utterance`/`_receive_response`
  functions (not reimplemented mock logic) against the live API: got a
  real reply back, correct transcript, correct audio byte count, correct
  mute/un-mute timing.

Real, confirmed model names on the account (`GET /v1/models`, filtered
for `realtime`): `gpt-realtime` (default), `gpt-realtime-1.5`,
`gpt-realtime-2`, `gpt-realtime-2.1`, `gpt-realtime-2.1-mini`,
`gpt-realtime-mini`, `gpt-realtime-translate`, `gpt-realtime-whisper`.

Memory save at session end uses a separate short-lived connection with a
duplicated (not shared — different transport) version of
`pixel_memory`'s summarization prompt, since `summarize_and_remember()`
expects a google-genai chat object.

**The transcript log includes what the student actually said, not just
Pixel's replies.** This wasn't true at first — `transcript_log` only
ever had `f"Pixel: {reply}"`, so memory extraction was completely blind
to the student's half of the conversation; a name only survived if
Pixel happened to repeat it back in a reply. Fixed by requesting
`"transcription": {"model": "whisper-1"}` on `session.audio.input` and
capturing `conversation.item.input_audio_transcription.completed`
(fires before `response.done` in practice). Verified live end-to-end: a
synthesized "my name is Saravana" utterance now shows up as
`transcript_log` as `"Student: ..."`, survives the summarization step,
and actually lands in `MEMORY.md`.

**Before running, check** (same as the other voice scripts):
`arecord -l` for your mic's card/device, a raw `arecord`/`aplay`
round-trip test — **at 24000 Hz this time, not 16000** — and
`PIXEL_MIC_DEVICE` set if `default` doesn't route to it. Same VAD knobs
apply: `PIXEL_VAD_START_RMS`, `PIXEL_VAD_SILENCE_MS`, `PIXEL_VAD_MIN_MS`.

Env vars: `OPENAI_API_KEY` (required), `OPENAI_REALTIME_MODEL` (default
`gpt-realtime`), plus the shared `PIXEL_MIC_DEVICE`/`PIXEL_VAD_*` vars.

**Cost**: audio tokens are priced much higher than text tokens, and a
long-running voice session means a turn's cost grows with however much
prior conversation the model has to carry as context. Two things
already in the code to keep that down:
- `max_output_tokens` is capped (default 600) so an occasional
  long-winded reply doesn't balloon audio-output cost — `PERSONA`
  already asks for short replies, this is just a hard backstop.
- The end-of-session memory save uses `output_modalities: ("text",)`,
  not audio — confirmed live that a text-only response shows
  `audio_tokens: 0` in its usage, since nobody ever hears that internal
  summary anyway.

The biggest lever is the model itself: `gpt-realtime-mini` (confirmed
available on the same key via `GET /v1/models`) is very likely
substantially cheaper per token than the full `gpt-realtime` — for
casual-chat-tier replies, that's probably the first thing to try if
cost matters more than voice quality. Set `OPENAI_REALTIME_MODEL=gpt-realtime-mini`.

**Debugging aid**: set `PIXEL_AUDIO_LOG_DIR` to save every sent
utterance as a timestamped WAV plus a `session_log.jsonl` line pairing
it with the reply text (`_log_utterance()`), so you can listen back
later and check for overlap/merged-utterance issues instead of guessing
from the reply alone — this is what would have made the earlier
"quadratic equation vs. your name" confusion instantly diagnosable.
Opt-in, unset by default — these are real voice recordings and the SD
card is small. Gitignored (`pixel-ai/audio_log/`), same as `MEMORY.md`.
Verified live: `_record_and_stream_utterance()` now returns the actual
recorded bytes (not just a chunk count) so there's something to save,
and the saved WAV round-trips correctly (right channels/width/rate,
matches the JSONL entry's `audio_file`/`utterance_ms`).

**Fixed severe ALSA underruns**: `base64`/`json` encode and decode for
every audio chunk — both sending mic audio and playing back the
reply — were running synchronously inline on the asyncio event loop,
competing with `aplay`'s write path for CPU on this single-core chip
and causing multi-second audible glitches. Moved both directions to
`run_in_executor` via two small helpers, `_encode_append_message()`
(send) and `_decode_and_play()` (combines decode + write + flush into
one executor dispatch, receive). Same fix applied to
`pixel_openai_voice_semantic.py` below (same root cause, worse there
since its receive loop never blocks waiting for a response). Re-ran
the existing multi-turn integration test against the live API after
the change — no correctness regression, both turns still completed
with correct transcripts — but the actual audio-glitch improvement on
real Pi hardware is still pending a hands-on test.

**Fixed Pixel hearing and transcribing its own voice as the student's
next turn.** A real session transcript on the Pi showed Pixel's own
phrases ("What's on your mind?", "Easy as that.") coming back verbatim
as `Student:` lines right after Pixel said them — a feedback loop, not
a transcription bug. Root cause: the mic un-mute after Pixel finishes
talking used a flat `0.5s` guess regardless of reply length, but the
real latency before audio is actually fully out of the speaker is the
OS pipe buffer plus `aplay`'s own `-B 500000` ALSA buffer — not
tightly bounded by that 500ms, especially for longer replies whose
audio deltas arrive faster than they play back. The mic would unmute
while Pixel's own trailing audio was still physically draining out,
get picked back up (no AEC on this hardware), and get misread as a new
turn. Fixed by tracking the actual decoded byte count of each reply and
computing a real wait time — `(bytes_total / (rate * width)) - elapsed
since playback started, plus a fixed 0.6s drain margin` — instead of a
fixed guess; `_decode_and_play()` now returns the decoded byte count so
the receive loop can accumulate it. Verified with a standalone test of
the formula against both a "burst" delivery pattern (all deltas
arriving before playback could possibly have kept up — the old flat
guess would leave the mic unmuted ~3s too early) and a "paced,
real-time" delivery pattern (where the old guess happened to be close
to right) — correctly waits out nearly the full remaining duration in
the first case and just the margin in the second, rather than a fixed
amount either way.

### OpenAI voice mode (semantic VAD): experimental, server-side turn detection

`pixel_openai_voice_semantic.py` is the experimental sibling to
`pixel_openai_voice.py` above. That one deliberately disables the
server's turn detection (`turn_detection: null`) in favor of our own
local silence-detection state machine, specifically to avoid repeating
the mistake of trusting a provider's server-side VAD blind (that's
exactly what killed `pixel_gemini.py`'s Live sessions after one turn).
This file makes the opposite choice — it trusts OpenAI's **semantic
VAD** to decide turn boundaries — after live-testing specifically to
confirm it isn't the same trap:

```bash
python pixel_openai_voice_semantic.py
```

**What was actually verified live before writing this** (not assumed):
- `eagerness: "low"` never advanced past `speech_started` for a
  synthetic tone (semantic VAD needs real linguistic content, not just
  loud audio — confirmed separately) and, even with real synthesized
  speech and a 5-second silence tail, got stuck indefinitely past 55+
  seconds without ever reaching `speech_stopped`.
- `eagerness: "medium"` completed turn 1 cleanly but turn 2 produced an
  **empty** `response.done` with `speech_stopped`/`committed`/
  `response.created` all missing — a flaky race, not just slow.
- `eagerness: "high"` completed two full, correct multi-turn cycles —
  twice over, repeated the test to be sure. That's the only one used
  here (`PIXEL_SEMANTIC_VAD_EAGERNESS`, default `high`) — don't change
  it without re-verifying the same way, since `low`/`medium` had real
  problems, not just slowness.
- Then ran the **actual production functions** from this file
  (`_session_update`, `_send_loop`, `_receive_loop`) against the live
  API with two real synthesized utterances fed through a queue exactly
  as `_capture_reader` would — first attempt truncated turn 1's reply
  because the test fed audio faster than real-time (not how a real mic
  behaves); fixed to realistic ~100ms-per-chunk pacing and both turns
  completed with full, correct transcripts.

**Architecturally this is not just a config change** from
`pixel_openai_voice.py` — enabling server-side turn detection means the
server decides when a turn starts/ends and auto-triggers responses, so
the send loop streams continuously (gated only by the no-AEC mute, not
by local amplitude thresholds) and the receive loop reacts to
`input_audio_buffer.speech_started`/`speech_stopped` events instead of
calling `.commit()`/`response.create()` itself. Closer in shape to
`pixel_gemini.py`'s loop than to `pixel_openai_voice.py`'s. The
`PIXEL_VAD_*` tuning vars don't apply here — there's no local VAD to
tune, the server does that now. `PIXEL_AUDIO_LOG_DIR` still works, just
buffers between `speech_started`/`speech_stopped` instead of using a
local state machine's own accumulation. Same input-transcription fix as
`pixel_openai_voice.py` applies here too — `transcript_log` captures
`"Student: ..."` via `conversation.item.input_audio_transcription.completed`,
not just Pixel's own replies, so memory extraction actually sees what
the student said.

**The real tradeoff**: `eagerness: "high"` is less patient about natural
mid-sentence pauses than `low`/`medium` would be if they worked —
closer to simple energy-based VAD with some semantic awareness layered
on top, not the "waits through thoughtful pauses" behavior that made
semantic VAD interesting in the first place. Whether that's worth it
over the proven manual version in `pixel_openai_voice.py` is a real
judgment call, not a clear upgrade.

### Ollama voice mode: fully local, no API costs, experimental

`pixel_ollama_voice.py` trades cloud quality for zero running cost and
no internet dependency: a separate always-on "fast machine" on the
same WiFi network runs both a local speech-to-text server
(`local_stt_server.py`, this repo) and [Ollama](https://ollama.com)
itself (LLaMA 3, Phi-3, or anything else Ollama can run). The Pi just
needs its USB mic, gTTS (already proven), and network access to that
machine — no OpenAI/Gemini API key touched at all.

**Why this needs two separate calls, not one.** Every other voice mode
in this repo uses a cloud model that understands audio directly
(Gemini's `generateContent`, OpenAI's Realtime API) — one call handles
both "what did the student say" and "what should Pixel reply."
LLaMA 3 / Phi-3 via Ollama are text-only, with no audio understanding
at all, so this mode needs an explicit speech-to-text step
(`faster-whisper`, behind a one-endpoint FastAPI server) before
anything reaches the LLM.

Setup, on the **fast machine** (not the Pi):
```bash
# Ollama itself: https://ollama.com -- not a pip package
ollama pull phi3:mini     # or llama3, or anything else you want to try
pip install -r requirements-llm-server.txt
python local_stt_server.py
```
Setup, on the **Pi**:
```bash
# in .env: PIXEL_STT_URL / PIXEL_OLLAMA_URL pointed at the fast
# machine's IP, PIXEL_OLLAMA_MODEL matching whatever you actually
# pulled (check with `curl http://<fast-machine-ip>:11434/api/tags`)
python pixel_ollama_voice.py
```

**Architecturally**, this reuses `pixel_gemini_voice.py`'s proven
local-VAD record-until-silence approach (no server-side VAD to debug)
for capturing the student's speech, since the STT-then-chat flow is
naturally turn-based on the input side. Ollama's `/api/chat` is
stateless per request — unlike Gemini's `chat` object, which keeps
history server-side — so this script keeps its own `messages` list
locally and resends it every turn, capped at `PIXEL_OLLAMA_MAX_HISTORY`
entries (default 20) so a long conversation doesn't make every turn
slower on what's likely a CPU-bound local model. Rename detection,
goodbye-phrase/idle-timeout session-ending, and memory summarization
all reuse the exact same `pixel_memory.py` functions as the OpenAI
scripts — one small improvement here: because `messages[0]` is just
local state rather than a server-side session, a mid-conversation
rename takes effect on *that same turn's* reply, not "starting next
turn" like the OpenAI scripts' documented limitation.

**On the output side, the reply is streamed and spoken sentence-by-
sentence**, not generated in full before anything is said.
`_stream_ollama_reply()` calls Ollama with `stream: true`, bridges the
synchronous `requests` streaming iterator into asyncio via a
background thread and a plain thread-safe queue, and speaks each
completed sentence (split on `.`/`!`/`?`) as soon as it's available —
the text-side equivalent of OpenAI's Realtime API streaming audio
deltas instead of waiting for a full response. `pixel_speaking` is
set once for the whole reply, not per sentence, so there's no mute/
unmute flicker between sentences. Added after live testing showed the
original blocking-until-done call made Pixel noticeably slower to
start talking than the OpenAI voice modes, especially for longer
replies on a CPU-bound local model. Verified the pipelining itself
with a mocked streaming worker that simulates realistic generation
delays: the first sentence was spoken at ~13% of the way through total
generation time, not only after it finished, confirming sentences
really do get spoken progressively rather than queued up and played
back after the fact.

**Live-verified independently once the actual fast machine was
available** — found and fixed two real bugs along the way:
- Ollama responded `model 'llama3' not found` — the fast machine only
  had `phi3:mini` pulled. `ollama pull <model>` and
  `PIXEL_OLLAMA_MODEL` just need to agree on an actually-installed
  model; confirmed a real `/api/chat` call against `phi3:mini` returns
  a correct reply.
- `local_stt_server.py`'s first live request crashed with
  `TypeError: open() got an unexpected keyword argument
  'metadata_errors'` — a `faster-whisper`/PyAV version incompatibility
  (PyAV >= 14 removed an argument `faster-whisper`'s bundled
  `decode_audio()` still passes; PyAV < 14 had no prebuilt wheel for
  this Python version and failed to build from source without MSVC
  Build Tools). Fixed by decoding the WAV ourselves via stdlib `wave`
  and handing `faster-whisper` a plain NumPy array instead of raw
  bytes — since we fully control the sender's format, that code path
  never touches PyAV at all. Verified the decode math against known
  sample values (mono and stereo) before the real re-test, then
  confirmed live: a real request now returns `200 OK` with no crash.

**Still not verified live**: the sentence-streaming pipeline itself
(confirmed correct against a mock, not yet run against the real
Ollama/STT servers together), and real speech transcription accuracy
on the actual Pi mic — the live tests so far used a synthetic tone,
which correctly round-tripped to empty text but isn't a real accuracy
test.

**Speech comes back via gTTS** (`pixel_tts.py`, same as every other
voice script) **by default** — a local Piper TTS alternative exists
(`pixel_tts_piper.py`, a new standalone module, same
`speak_async()`/`cleanup_speech()` interface as `pixel_tts.py`, so
switching `_speak_sentence()` over is a one-line import change) but
isn't wired in by default, since the current dev hardware is a Pi 1
B+ and Piper's `onnxruntime` dependency has no prebuilt wheel for
ARMv6 — it would fail to install there at all. Built after comparing
this mode against
[mayukh4/pibot_local_agent](https://github.com/mayukh4/pibot_local_agent),
a similar Pi voice-assistant project that uses Piper specifically to
avoid gTTS's per-sentence network round-trip to Google's cloud TTS
endpoint, which both adds latency on top of the sentence-streaming
pipeline above and contradicts this mode's whole "fully local, zero
API cost" point. **Worth switching to** (`import pixel_tts_piper as
pixel_tts` in place of `import pixel_tts`) **on Pi Zero 2 W / Pi 3 B+
or newer** (armv7l/aarch64), the documented production target.
Verified so far: the module's own synthesize/voice-loading logic
against a stubbed Piper voice (produces a correctly-formed WAV, caches
the loaded model instead of reloading per call, raises a clear error
if `PIXEL_PIPER_VOICE` isn't set) and that the conversation loop
(rename, goodbye-ends-session, sentence-streamed replies) still works
correctly with it wired in — not yet run with a real Piper voice model
on real Pi audio hardware.

**A scoped-down router now answers some things without any Ollama
call at all.** `pixel_ollama_router.py` is a new standalone module,
checked right after transcription and before the message goes into
`messages`/Ollama — time/date questions and "how are you feeling"
system-status questions get answered instantly from real Python/OS
data (`/proc/uptime`, `/proc/meminfo`, `/sys/class/thermal/...`), with
zero LLM round-trip. Deliberately scoped down from
`pibot_local_agent`'s router, which also uses Ollama's structured
tool-calling (plus a keyword fallback) to route weather/news/jokes to
API-backed tools and hands complex questions to a cloud model — we
don't have those API keys wired up, and didn't want this mode's "zero
cost" story to quietly grow a cloud fallback, so this is keyword
matching only (same pattern-list approach as `pixel_memory.py`'s
rename/goodbye detection) for the two things that make sense with zero
API keys. Still recorded into `messages`/`transcript_log` exactly like
a normal Ollama-answered turn, so later conversation context and
memory summarization both see it. Verified against the real
`_conversation_loop`: fast-path questions never reach
`_ollama_chat_stream_worker()` at all, both get spoken correctly, and
both land in `messages` and `transcript_log` for later turns.

**Full 4-tier routing for a "basic" (free) user**, once that zero-cost
fast path above has already ruled itself out — cheapest/fastest to
most expensive, each one falling back to the next if it fails:

1. **`local`** — the fast path above (time/date, system status). Zero
   LLM call.
2. **`learnx`** — curriculum math/physics/chemistry questions
   (`pixel_ollama_router.classify()`'s keyword match), answered by
   `pixel_brain.ask()` (the same LearnX chat client the keyboard mode
   uses) instead of a generic model, since that's what LearnX is
   actually specialized for. Lazily imports `pixel_brain` only when
   this tier is actually hit — `pixel_brain` → `config` fails fast if
   `LEARNX_API_KEY`/`LEARNX_USER_ID` aren't set, which is right for
   the LearnX-only scripts but shouldn't be a hard requirement just to
   run this mode's router at all. If it's not configured (or the call
   fails for any reason), falls back to the cloud tier automatically.
3. **`cloud`** — general-knowledge/complex questions a tiny local
   model handles poorly (`pixel_ollama_cloud.py`, a new standalone
   module), via a plain OpenAI chat completion — deliberately *not*
   the Realtime API, since the audio side is already handled
   elsewhere here. **Important**: a ChatGPT/Claude/Gemini
   *subscription* does not cover this — API calls are billed
   separately per token regardless of any consumer subscription.
   Reuses the existing `OPENAI_API_KEY` already set for the OpenAI
   voice scripts; `PIXEL_CLOUD_MODEL` picks a cheap/fast model,
   **not yet confirmed live** against a real account (same
   verify-live-don't-guess approach as the Realtime model names
   elsewhere in this file — check `GET /v1/models` before relying on
   the default). If this call fails, falls back to the `llm` tier.
4. **`llm`** — the local Ollama model, exactly as before (including
   the sentence-streaming pipeline). The ultimate fallback if every
   tier above either didn't match or failed.

Every question, regardless of which tier answers it, gets logged via
`pixel_ollama_router.log_routing()` — printed to console
(`[router] <tier> (<model>) -> '<question>'`) and appended to a
gitignored `persona/routing_log.jsonl`
(`{timestamp, tier, model, question, reply}` per line), including
which *specific* model handled it, not just the tier name: the actual
`PIXEL_OLLAMA_MODEL` for `llm`, the actual `PIXEL_CLOUD_MODEL` for
`cloud`, `"learnx-backend"` for `learnx` (LearnX doesn't report which
underlying model it used, so that's as specific as it gets), and
`None` for `local` (a plain Python function, no model involved).
Verified all four tiers log the correct model value against the real
`_conversation_loop`.

**A "premium" user instead skips this router entirely** and talks
through the OpenAI Realtime pipeline (`pixel_openai_voice.py` /
`pixel_openai_voice_semantic.py`) directly — paying for a better model
buys smarter LearnX-hand-off judgment (via that model's own
tool-calling deciding when a question needs LearnX, not a keyword
guess) instead of a cost-minimizing keyword router. **Not built yet**
— this needs OpenAI Realtime function/tool-calling wired into the
websocket flow, genuinely new protocol surface for this project (the
existing Realtime scripts only ever do plain conversational turns, no
tool calls), so it's a separate, more involved piece of work than the
basic-tier router above.

Verified the full fallback chain (`learnx` → `cloud` → `llm`) against
the real `_conversation_loop` with four scenarios: LearnX succeeding
(no cloud/llm call at all), LearnX failing and falling back to cloud,
cloud failing and falling back to llm, and an ordinary casual question
going straight to `llm` without ever attempting learnx/cloud. Also
verified the classifier against 19 example questions (7
curriculum/learnx, 6 complex/cloud, 6 casual/llm) and that
`log_routing()` writes correctly-structured JSONL. Not yet verified:
real LearnX/cloud API calls against live credentials, and real-world
classification accuracy on actual spoken questions rather than typed
examples.

**Three scripted moments, same idea as `pibot_local_agent`'s
pre-generated filler WAVs** (adapted to gTTS instead of pre-rendering
audio files, since this mode's replies are already synthesized live):
- **Startup**: `_STARTUP_MESSAGE` is spoken once, directly via
  `_speak_sentence()`, before the listening loop even starts — not
  re-spoken on reconnects or on every goodbye-triggered fresh
  conversation, just the one "I just booted" greeting.
- **Thinking filler**: right after a question is confirmed to need
  one of the three *real* (slow) tiers — `learnx`/`cloud`/`llm` all
  involve a genuine network/model call — a random pick from
  `_THINKING_FILLERS` plays first, masking that wait instead of dead
  air. The zero-cost `local` fast path (time/status) skips this
  entirely, since there's no wait to hide there.
- **Goodbye**: a goodbye utterance is no longer routed through any
  tier at all — it goes straight to a random pick from
  `_GOODBYE_PHRASES` instead of whatever the LLM/cloud/LearnX might
  improvise, both for a consistent farewell and to skip a pointless
  call for a fixed social closing.

Verified against the real `_conversation_loop`: a goodbye speaks
exactly one scripted farewell with no filler or tier call at all, a
real-tier question speaks the filler then the actual reply (two
separate spoken pieces, in that order), the instant local fast path
speaks no filler, and the startup message is spoken exactly once
before the listening loop begins.

### Gemini text mode: same casual chat, no mic required

`pixel_gemini_text.py` is the keyboard fallback for when there's no
working mic yet (e.g. the USB headset isn't recognized) — same persona
and intent as `pixel_gemini.py`, LearnX still paused, just typed input
instead of live audio, and Gemini's regular chat API
(`client.chats.create()`/`chat.send_message()`, built-in multi-turn
history) instead of the Live API:

```bash
python pixel_gemini_text.py
```

Replies are spoken aloud via the same gTTS+mpg123 pipeline
`pixel_main.py` uses for its gTTS fallback path. The persona instruction
explicitly bans markdown/LaTeX in the prompt itself, since Gemini's
regular text replies have no backend-side cleanup step the way LearnX's
chat-audio endpoint does — if it ever slips in formatting anyway, gTTS
will read it out literally.

Env vars: `GEMINI_API_KEY` (required), `GEMINI_TEXT_MODEL` (default
`gemini-3.8-flash` — `gemini-2.5-flash` 404s now, deprecated for new
users as of this writing).

Typing while Pixel is still speaking cuts it off immediately and sends
what you typed as the next message (`_speak_and_listen`, same barge-in
pattern as `pixel_discussion.py`) — speaking and listening run on
separate threads and race each other rather than one blocking the other.

### Persistent memory across restarts

`pixel_memory.py` is what makes Pixel remember things between separate
runs of `pixel_gemini_text.py` — without it, `client.chats.create()`'s
history only lasts for one running process. Two plain files in
`persona/`, same spirit as OmniBot's persona-file pattern:

- `IDENTITY.md` — Pixel's own generic personality. Safe to commit, no
  personal data.
- `MEMORY.md` — facts about the specific student (name, interests,
  ongoing projects). **Gitignored, never committed** — this is personal
  data, created on first write if it doesn't exist yet.

Both get read into the system instruction at startup
(`pixel_memory.load_context()`). At the end of each session, one extra
model call (`summarize_and_remember()`/`apply_summary()`) asks for at
most 3 short, durable things worth keeping from that conversation —
not after every turn, to keep cost down and avoid cluttering memory
with one-off small talk ("NOTHING" if there's nothing worth keeping).

**`MEMORY.md` is split into two sections, not one flat list.** A
`## Current` section holds stable key/value facts (name, grade, a
recurring interest) that get **replaced** when the model reports an
updated value for the same key — fixes the earlier problem where a
corrected name just sat next to the stale one forever. A `## History`
section is the dated, append-only log of one-off things worth carrying
forward (unfinished topics, promises, shared moments). The
summarization prompt asks the model to tag each line `CURRENT: key:
value` or `EVENT: <text>`; `apply_summary()` routes each to the right
section, and still keeps an untagged line (as an event) rather than
silently dropping it if the model doesn't follow the format exactly.
Old flat-format `MEMORY.md` files (no headers at all) are read as pure
history on first load — nothing already saved is lost by the format
change. Verified with a standalone test covering: old-format
backward-compat, a repeated key replacing instead of duplicating, event
appends, all three `apply_summary()` routing cases, and the `NOTHING`
no-op.

**Raw per-session transcripts are now saved to `persona/transcripts/`
before summarization is even attempted** (`pixel_memory.save_transcript()`),
not just held in an in-memory list that died with the process. A
crashed or failed summarization call used to mean that session's
conversation was gone for good; now the raw text survives regardless,
as a safety net for re-summarizing later if needed. Gitignored
(`pixel-ai/persona/transcripts/`), same sensitivity as `MEMORY.md`.

**A real end-of-conversation signal, not just Ctrl+C/a crash.** Both
OpenAI voice scripts' outer loop reconnects on every `Exception` except
`KeyboardInterrupt` — so without this, memory summarization never fired
during normal continuous use, only when you manually stopped the
script. Two ways a conversation now ends on its own, both of which
save memory and start fresh (reloading `MEMORY.md`, so the very next
conversation already has it):
- **Saying goodbye** — `pixel_memory.detect_goodbye()` checks the
  student's transcribed speech for common sign-offs ("bye", "see you
  later", "that's all for today", "gotta go", etc.), same pattern-list
  approach and same caveat as rename detection. The session only ends
  *after* that turn's farewell reply has fully played, not mid-sentence.
- **Idle timeout** (`PIXEL_IDLE_TIMEOUT_S`, default 300s) — a
  `_idle_watchdog()` coroutine runs alongside the mic/playback loops
  and ends the conversation if nothing real has happened for that long,
  for when the student just walks away without saying anything. Not
  the same bug as the no-AEC echo loop fixed above — this coroutine
  only reacts to the shared `last_activity` timestamp, which real
  speech-detection events refresh.

Both raise a dedicated `_SessionEnd` exception, caught separately from
real connection errors in `run()`'s reconnect loop — a dropped
connection still just reconnects silently, only a deliberate session
end triggers a memory save. Verified the idle-timeout timing logic
standalone (does not fire early, an activity reset correctly delays
it, does fire after a real idle period) and the goodbye regex against
13 realistic sign-off phrasings plus negatives — the full live path
(goodbye mid-conversation actually ending it on real hardware) is
still pending a hands-on test.

**Renaming Pixel** (both `pixel_openai_voice.py` and
`pixel_openai_voice_semantic.py` support this): say something like
"your name is now Bolt" or "I'll call you Rex" and
`pixel_memory.detect_rename_request()` picks it up from your
transcribed speech, persists it to `persona/NAME.txt` (gitignored, same
reasoning as `MEMORY.md` — a live local customization, not generic
shared identity), and pushes a fresh `session.update` so the rest of
that same session uses the new name — not just future runs. This is a
plain local pattern-matcher for common phrasings, not full language
understanding — the model itself deciding via a declared tool call
would handle phrasing variety better, but that's unverified new
protocol surface; this is the simpler, already-provable option.
Verified live end-to-end through the actual production functions:
saying "your name is now Bolt" correctly persisted it, and the very
next turn in the same session replied "my name's Bolt" — confirmed the
regex also correctly ignores the student stating their *own* name
("my name is Saravana" never triggers a rename).

**Pattern list broadened after a real session log showed two missed
phrasings**: "I need to name you as Chitty" and "I changed your name to
Chitti" — neither matched the original "your name is"/"I'll call
you"/etc. list. Added patterns for "I changed/am changing your name
to", "I need/want to name/call/rename you (as)", and "I'm naming you".
Re-verified against 18 cases (all the original phrasings, both missed
real-world ones, and the negative "my name is ..." case) before and
after the change — still just a growing pattern list, not understanding,
so new real phrasings can still slip through; a tool-call-based
approach remains the more robust unverified alternative mentioned
above.

**Memory now also captures the conversation itself, not just static
facts about the student.** The summarization prompt (shared by
`pixel_memory.py`, `pixel_openai_voice.py`, and
`pixel_openai_voice_semantic.py`) originally only asked for facts like
name/interests/projects. Broadened to also ask for things worth
carrying forward from the conversation — an unfinished topic to pick
back up, something Pixel promised to follow up on, a running joke or
shared moment — so Pixel reads more like a continuous friend than a
device that resets context every session. `load_context()`'s framing
updated to match ("...your ongoing friendship"). Verified live: a
transcript with an unfinished "factoring quadratics, pick it up
tomorrow" thread, a durable interest ("likes robotics"), and a trivial
weather exchange correctly kept the first two and dropped the weather
one.

### Discussion mode: chunked, paced delivery of any reply

`pixel_discussion.py` is another separate standalone script, same
non-interfering approach as `pixel_ladder.py`:

```bash
python pixel_discussion.py
```

The backend's guided-discovery logic only sometimes asks a real question
and waits — plenty of conceptual questions still just get a full direct
explanation (`ladder_depth` stays 0). This mode doesn't depend on that:
it splits ANY reply into its own natural structure (the `###` headings
and `---` dividers the backend already tends to use for longer
explanations — a short answer with neither stays one chunk) and delivers
one piece at a time, pausing after each to check in. Pressing enter (or
saying "continue"/"more") just advances to the next piece with no network
call; typing anything else sends it to the backend as the next turn in
the same conversation, abandoning whatever pieces were left — so the
student can genuinely branch instead of clicking through a fixed script.
Speech for each chunk uses a local, rougher markdown/LaTeX cleanup
(`_clean_for_speech`) since the backend's own cleanup endpoint only voices
a whole stored message, not a partial chunk — formula pronunciation isn't
as polished as the full-message path `pixel_main.py` uses.

**True barge-in:** Pixel speaks and listens at the same time
(`_speak_and_listen`) — the input prompt appears on screen the instant a
chunk starts, not after it finishes, and playback is cut off immediately
the moment you start answering. You're never stuck waiting for Pixel to
finish talking before you can respond, mid-sentence or not.

**Replies are asked to stay short and conversational.** `pixel_brain.ask()`
wraps every outgoing message with an instruction telling the model it's a
voice-only companion robot, not a web page — 1-3 short sentences, no
headings/bullets/LaTeX unless asked for the math. There's no "voice mode"
field on `/api/chat/send` to flip instead, so this is the only lever
available without changing shared backend behavior; the tradeoff is that
this instruction text becomes part of the stored conversation history
alongside the student's actual words, same as any other turn.

### Not yet implemented (explicitly out of scope for Phase 1)

- Real game generation (`pixel_game.py` is a stub).
- Azure TTS (there's no public Azure-TTS-for-arbitrary-text endpoint on
  the backend — chat replies are voiced via the existing OpenAI tts-1
  chat-audio endpoint instead; ad-hoc local phrases still use gTTS).
- Any ST7789/I2S mic/speaker hardware code.

## Phase 2 (when hardware arrives)

- Swap `pixel_listen.py`'s `listen()` from keyboard to the ZTS6631 I2S mic.
- Swap `pixel_tts.py`'s playback device from `mpg123` to the MAX98357A
  I2S speaker (synthesis sources — backend chat-audio + gTTS fallback —
  stay the same).
- Swap `pixel_face.py`'s render target from the HDMI window to the ST7789
  SPI display.

## Phase 3 (production)

Port the same code to a Raspberry Pi Zero 2 W, fully wireless, in Pixel's
physical body.
