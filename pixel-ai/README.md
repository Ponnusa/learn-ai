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
