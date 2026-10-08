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

### Gemini mode: real-time voice conversation (LearnX paused)

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
Gemini call (`summarize_and_remember()`) asks the model to pull out at
most 3 short, durable facts worth keeping from that conversation and
appends them to `MEMORY.md` — not after every turn, to keep cost down
and avoid cluttering memory with one-off small talk ("NOTHING" if there's
nothing worth keeping). Verified the file I/O and summarization parsing
with a mocked chat session before shipping.

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
