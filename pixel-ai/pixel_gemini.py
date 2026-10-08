"""Pixel's casual conversational layer: Gemini Live, real-time voice.

Standalone, new file — doesn't touch any existing pixel_*.py (only
imports pixel_face for shared visual states) and does NOT import
config.py, since that fails fast without LEARNX_API_KEY/LEARNX_USER_ID —
LearnX is paused for this module entirely, by request.

Requires a USB headset for mic input (confirmed working; the Pi's own
3.5mm jack is output-only and has no capture capability at all),
`pip install google-genai`, and GEMINI_API_KEY set.

Captures/plays audio via `arecord`/`aplay` subprocess rather than PyAudio
— same reasoning pixel_tts.py already used shelling out to mpg123 instead
of a Python audio-playback library: avoids PortAudio's native bindings on
this ARM hardware, reusing tools already proven to work here.

Audio contract with the Live API, per current docs — the exact response
shape can vary by installed SDK version, so _extract_audio() below checks
multiple possible fields defensively rather than assuming one:
  - send:    16-bit PCM, 16kHz, mono, little-endian, raw (no WAV header)
  - receive: 16-bit PCM, 24kHz, mono, little-endian, raw

No LearnX routing yet — this is pure Gemini casual conversation for now.
The "defer to LearnX for real science questions" split is a follow-up
once this base layer is confirmed working end-to-end on real hardware.
"""
import asyncio
import os
import subprocess

from dotenv import load_dotenv
from google import genai
from google.genai import types

from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_TALKING

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
# Confirmed against the real key via GET /v1beta/models?pageSize=1000,
# filtered for "bidiGenerateContent" in supportedGenerationMethods — not
# guessed. Other live-capable options on this key as of the check:
# gemini-3.1-flash-live-preview, gemini-3.8-live (newest generation),
# gemini-3.8-live-extended-thinking, gemini-3.5-live-translate-preview.
# Model names shift fast — re-run that same query if this one 404s.
MODEL = os.environ.get("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest")
# `arecord -l` to find your USB headset's card/device, e.g. "plughw:1,0".
CAPTURE_DEVICE = os.environ.get("PIXEL_MIC_DEVICE", "default")

SEND_RATE = 16000
RECEIVE_RATE = 24000
_CHUNK_MS = 100
_CHUNK_BYTES = int(SEND_RATE * 2 * _CHUNK_MS / 1000)  # 16-bit = 2 bytes/sample

PERSONA = (
    "You're Pixel, a friendly, casual desk companion robot for a student. "
    "Keep replies short and conversational, like a real spoken chat with "
    "a curious friend, not a lecture. Warm, a little playful, genuinely "
    "interested in what the student says."
)


def _start_capture() -> subprocess.Popen:
    return subprocess.Popen(
        ["arecord", "-D", CAPTURE_DEVICE, "-f", "S16_LE", "-r", str(SEND_RATE),
         "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


def _start_playback() -> subprocess.Popen:
    return subprocess.Popen(
        ["aplay", "-f", "S16_LE", "-r", str(RECEIVE_RATE), "-c", "1", "-t", "raw", "-"],
        stdin=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


async def _send_mic_audio(session, capture_proc: subprocess.Popen) -> None:
    loop = asyncio.get_event_loop()
    while True:
        chunk = await loop.run_in_executor(None, capture_proc.stdout.read, _CHUNK_BYTES)
        if not chunk:
            break
        await session.send_realtime_input(
            audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={SEND_RATE}")
        )


def _extract_audio(response) -> bytes | None:
    """Pull raw audio bytes out of a Live API response, whichever shape
    the installed SDK version uses."""
    data = getattr(response, "data", None)
    if data:
        return data
    server_content = getattr(response, "server_content", None)
    model_turn = getattr(server_content, "model_turn", None) if server_content else None
    if model_turn:
        for part in model_turn.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data
    return None


def _is_turn_complete(response) -> bool:
    server_content = getattr(response, "server_content", None)
    return bool(getattr(server_content, "turn_complete", False)) if server_content else False


async def _receive_and_play(session, playback_proc: subprocess.Popen) -> None:
    async for response in session.receive():
        audio_bytes = _extract_audio(response)
        if audio_bytes:
            face.set_state(STATE_TALKING)
            playback_proc.stdin.write(audio_bytes)
            playback_proc.stdin.flush()
        if _is_turn_complete(response):
            face.set_state(STATE_LISTENING)


async def run() -> None:
    client = genai.Client(api_key=GEMINI_API_KEY)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=PERSONA,
    )

    capture_proc = _start_capture()
    playback_proc = _start_playback()
    face.start()
    face.set_state(STATE_LISTENING)

    print("Pixel is listening (USB headset). Ctrl+C to stop.")
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            await asyncio.gather(
                _send_mic_audio(session, capture_proc),
                _receive_and_play(session, playback_proc),
            )
    finally:
        capture_proc.terminate()
        playback_proc.stdin.close()
        playback_proc.terminate()
        face.set_state(STATE_IDLE)
        face.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
