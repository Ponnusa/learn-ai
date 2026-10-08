"""Pixel's voice mode: record-until-silence + generateContent, no Live API.

Standalone, new file -- same non-interfering pattern as the other
pixel_*.py mode scripts.

Deliberately does NOT use the Gemini Live API. Extensive testing on
pixel_gemini.py showed Live sessions reliably produce exactly one good
reply, then permanent silence until an idle timeout forces a reconnect
-- reproduced identically across two different models
(gemini-2.5-flash-native-audio-latest and gemini-3.8-live), with
conclusive proof (a corrected heartbeat log showing audio continuously
and successfully reaching the server for 30+ seconds with zero
response) that this is a server-side session-handling issue, not
something fixable from the client.

This sidesteps the problem entirely: no persistent streaming session, no
server-side voice activity detection. Turn-based instead, built from
pieces already proven reliable tonight:
  - arecord for capture, continuously drained by a background task so
    it never blocks regardless of what the conversation loop is doing
    (pixel_gemini.py)
  - simple LOCAL silence detection (stdlib audioop.rms) to decide when
    one utterance is finished -- fully within our own control/visibility,
    no opaque server VAD to debug
  - the recorded clip sent as a WAV Part to the SAME chat session
    pixel_gemini_text.py uses (client.chats.create()/chat.send_message())
    -- same persona, same persistent memory via pixel_memory.py
  - the reply spoken via pixel_tts's async primitives, with mic input
    muted while Pixel is talking -- no AEC on this hardware, same
    echo-prevention reasoning as pixel_gemini.py

Requires a working USB mic (confirmed via `arecord -l` + a raw
arecord/aplay round-trip test) and GEMINI_API_KEY set. LearnX stays
paused, like the other Gemini scripts.
"""
import asyncio
import audioop  # stdlib; deprecated (PEP 594) but still present on 3.11,
                # removal isn't until 3.13 -- replace with manual RMS if
                # this ever moves to a newer Python.
import io
import logging
import os
import subprocess
import wave

from dotenv import load_dotenv
from google import genai
from google.genai import types

import pixel_memory
import pixel_tts
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
# `arecord -l` to find your mic's card/device, e.g. "plughw:3,0".
CAPTURE_DEVICE = os.environ.get("PIXEL_MIC_DEVICE", "default")

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit
_CHUNK_MS = 100
_CHUNK_BYTES = int(SAMPLE_RATE * SAMPLE_WIDTH * _CHUNK_MS / 1000)

# Tune these if it's too trigger-happy or too insensitive -- ambient
# noise floor and real speech level both vary a lot by mic/room.
_START_RMS = int(os.environ.get("PIXEL_VAD_START_RMS", "300"))
_END_SILENCE_MS = int(os.environ.get("PIXEL_VAD_SILENCE_MS", "800"))
_MAX_UTTERANCE_MS = 20000
_PRE_ROLL_CHUNKS = 3  # ~300ms kept from just before speech is detected,
                      # so the first word doesn't get clipped off.

PERSONA = (
    "You're Pixel, a friendly, casual desk companion robot for a student. "
    "Keep replies short and conversational, like a real spoken chat with "
    "a curious friend, not a lecture. Warm, a little playful, genuinely "
    "interested in what the student says. Plain spoken sentences only — "
    "no markdown, no bullet points, no headings, no LaTeX — this gets "
    "read aloud by a text-to-speech engine that can't pronounce symbols. "
    "Each audio clip may contain more than one thing the student said — "
    "if they change topic or ask something unrelated partway through "
    "(like your name, or a personal question), answer THAT directly "
    "first, don't just keep riding the previous topic's momentum."
)


def _start_capture() -> subprocess.Popen:
    return subprocess.Popen(
        ["arecord", "-D", CAPTURE_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
         "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )


def _stop_proc(proc: subprocess.Popen | None, timeout: float = 2) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _pcm_to_wav(pcm_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


async def _capture_reader(capture_proc: subprocess.Popen, queue: "asyncio.Queue[bytes]") -> None:
    """Continuously drains arecord into the queue -- runs for the whole
    session regardless of what the conversation loop is doing, so the
    capture pipe never backs up during a slow Gemini call or a long
    reply being spoken."""
    loop = asyncio.get_event_loop()
    while True:
        chunk = await loop.run_in_executor(None, capture_proc.stdout.read, _CHUNK_BYTES)
        if not chunk:
            raise RuntimeError(f"arecord exited unexpectedly (exit code {capture_proc.poll()})")
        await queue.put(chunk)


async def _record_utterance(queue: "asyncio.Queue[bytes]", pixel_speaking: asyncio.Event) -> bytes:
    """Waits for speech to start, buffers it, returns once enough
    trailing silence has passed. Chunks arriving while Pixel itself is
    talking are discarded, not treated as user speech -- no AEC on this
    hardware, same reasoning as pixel_gemini.py's mute."""
    pre_roll: list[bytes] = []
    buffer: list[bytes] = []
    recording = False
    silence_ms = 0

    while True:
        chunk = await queue.get()

        if pixel_speaking.is_set():
            pre_roll.clear()
            continue

        rms = audioop.rms(chunk, SAMPLE_WIDTH)

        if not recording:
            pre_roll.append(chunk)
            if len(pre_roll) > _PRE_ROLL_CHUNKS:
                pre_roll.pop(0)
            if rms >= _START_RMS:
                recording = True
                buffer = list(pre_roll)
                silence_ms = 0
            continue

        buffer.append(chunk)
        silence_ms = silence_ms + _CHUNK_MS if rms < _START_RMS else 0

        total_ms = len(buffer) * _CHUNK_MS
        if silence_ms >= _END_SILENCE_MS or total_ms >= _MAX_UTTERANCE_MS:
            return b"".join(buffer)


async def _speak(text: str, pixel_speaking: asyncio.Event) -> None:
    """gTTS + playback, with mic forwarding muted for the duration (plus
    a short tail so aplay's buffered remainder finishes before
    un-muting) -- same echo-prevention pattern as pixel_gemini.py."""
    pixel_speaking.set()
    loop = asyncio.get_event_loop()
    try:
        proc, path = await loop.run_in_executor(None, pixel_tts.speak_async, text)
        if proc is not None:
            await loop.run_in_executor(None, proc.wait)
        pixel_tts.cleanup_speech(path)
    finally:
        await asyncio.sleep(0.3)
        pixel_speaking.clear()


async def _conversation_loop(
    chat, queue: "asyncio.Queue[bytes]", pixel_speaking: asyncio.Event, transcript: list[str]
) -> None:
    loop = asyncio.get_event_loop()
    while True:
        face.set_state(STATE_LISTENING)
        audio_bytes = await _record_utterance(queue, pixel_speaking)
        utterance_ms = len(audio_bytes) / (SAMPLE_RATE * SAMPLE_WIDTH) * 1000
        # No visibility before this into what was actually captured per
        # utterance -- a long recording (several unrelated sentences
        # merged because a pause between them was under
        # PIXEL_VAD_SILENCE_MS) and "captured cleanly but the model
        # stayed anchored to prior context" look identical from the
        # reply alone. This at least tells us which one happened.
        logger.info("utterance captured: %.0fms of audio", utterance_ms)

        face.set_state(STATE_THINKING)
        wav_bytes = _pcm_to_wav(audio_bytes)
        try:
            response = await loop.run_in_executor(
                None, chat.send_message,
                [types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")],
            )
            reply = response.text or ""
        except Exception:
            logger.exception("Gemini send_message failed")
            continue

        print(f"Pixel: {reply}")
        face.set_state(STATE_TALKING)
        await _speak(reply, pixel_speaking)
        transcript.append(f"Pixel: {reply}")


async def run() -> None:
    client = genai.Client(api_key=GEMINI_API_KEY)
    system_instruction = PERSONA
    remembered = pixel_memory.load_context()
    if remembered:
        system_instruction = f"{PERSONA}\n\n{remembered}"
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )

    face.start()
    print("Pixel is listening (USB mic). Ctrl+C to stop.")
    transcript: list[str] = []
    try:
        while True:
            capture_proc = _start_capture()
            pixel_speaking = asyncio.Event()
            queue: "asyncio.Queue[bytes]" = asyncio.Queue()
            try:
                await asyncio.gather(
                    _capture_reader(capture_proc, queue),
                    _conversation_loop(chat, queue, pixel_speaking, transcript),
                )
            except Exception:
                logger.exception("Mic capture failed -- restarting")
                print("Mic capture dropped — restarting...")
            finally:
                _stop_proc(capture_proc)
            await asyncio.sleep(2)
    finally:
        pixel_memory.summarize_and_remember(chat, transcript)
        face.set_state(STATE_IDLE)
        face.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
