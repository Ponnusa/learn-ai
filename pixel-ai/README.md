# Pixel AI

An AI desk-companion robot for students — a peer learning friend, not a
tutor. Built by nordX Labs Oy (Helsinki), connects to the LearnX AI
platform (learnx-ai.com, this repo's `backend/`).

## Phase 1 (current): Raspberry Pi 1 B+, keyboard input, HDMI face

Hardware: Pi 1 B+, 700MHz ARMv6, 512MB RAM, Pi OS Legacy Lite 32-bit,
Python 3.11.2, ethernet, HDMI out, 3.5mm audio out. No mic/speaker/display
hardware is connected yet, so this phase uses a keyboard and an HDMI
pygame window instead.

### Prerequisite: a LearnX API key

The video endpoints (`/api/public/v1/videos/...`) require a real,
approved API key from the `api_keys` table (`Authorization: Bearer
lx_live_...`). This must be provisioned on the backend/DB side before
Pixel can request animations — it isn't something this folder's code can
create for itself. `/api/chat/send` and `/api/uploads` need no auth
header, just a `user_id`.

### Setup on the Pi

```bash
cd pixel-ai
source /home/pi/pixel_env/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in LEARNX_API_KEY and LEARNX_USER_ID
python pixel_main.py
```

### What works today

- Type a question -> `POST /api/chat/send` -> gTTS speaks the reply, face
  animates (idle/listening/thinking/talking/happy) on the HDMI window.
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
