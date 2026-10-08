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
  gTTS speaks just the first couple of sentences (`pixel_tts.summarize_for_speech`)
  to keep narration short, face animates (idle/listening/thinking/talking/happy)
  on the HDMI window.
- `video: <word problem>` -> `POST /api/public/v1/videos/generate`, polls
  `GET /api/public/v1/videos/{id}` (~60s), prints the resulting URL. No
  local video player is wired up yet — that's a later phase.
- A photo can be POSTed to `http://<pi-ip>:5005/photo` (multipart field
  `photo`, optional `question`) — forwards to `/api/uploads` then
  `/api/chat/send` with `image_url` set, speaks the reply back.
- `game: <topic>` reports that game generation isn't available — the
  LearnX backend has no game-code-generation endpoint today. Would need
  new backend work, not just a new client.

### Not yet implemented (explicitly out of scope for Phase 1)

- Real game generation (`pixel_game.py` is a stub).
- Azure TTS (sticking with gTTS even once hardware arrives — there's no
  public Azure-TTS-for-arbitrary-text endpoint on the backend).
- Any ST7789/I2S mic/speaker hardware code.

## Phase 2 (when hardware arrives)

- Swap `pixel_listen.py`'s `listen()` from keyboard to the ZTS6631 I2S mic.
- Swap `pixel_tts.py`'s playback device from `mpg123` to the MAX98357A
  I2S speaker (synthesis stays gTTS).
- Swap `pixel_face.py`'s render target from the HDMI window to the ST7789
  SPI display.

## Phase 3 (production)

Port the same code to a Raspberry Pi Zero 2 W, fully wireless, in Pixel's
physical body.
