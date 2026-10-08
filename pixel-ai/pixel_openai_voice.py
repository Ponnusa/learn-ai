"""Pixel's voice mode via OpenAI's Realtime API, with local (not server) VAD.

Standalone, new file -- same non-interfering pattern as the other
pixel_*.py mode scripts. An alternative transport to
pixel_gemini_voice.py: this one DOES use a persistent streaming
WebSocket (unlike the turn-based generateContent approach there), but
deliberately disables OpenAI's server-side turn detection
(turn_detection: null) in favor of the SAME local silence-detection
state machine already proven in pixel_gemini_voice.py. After watching
Gemini's server-side VAD silently break after exactly one turn, this
avoids trusting a second provider's server VAD blind.

Everything below was verified live against the real API with a working
key before writing this file, not guessed from docs/search (which kept
surfacing stale/conflicting info -- a real Beta vs GA split with
different event names):
  - wss://api.openai.com/v1/realtime?model=<model>,
    Authorization: Bearer <key> only -- no OpenAI-Beta header needed,
    confirmed this account speaks the current (GA) wire format.
  - Real event names on this account: response.output_audio.delta,
    response.output_audio_transcript.delta (NOT the older
    response.audio.delta/response.text.delta beta names).
  - session.update requires an explicit "type": "realtime" field and a
    nested session.audio.input/output.format structure. Input rate must
    be >=24000 (confirmed via a real "integer below minimum value"
    error when 16000 was tried) -- unlike Gemini's asymmetric
    16kHz-in/24kHz-out, this API wants 24kHz for both directions.
  - The manual-turn flow (input_audio_buffer.append -> .commit ->
    response.create, with turn_detection: null) was tested end-to-end
    with synthetic audio and got a real "PONG" reply back with
    response.done status "completed".

Requires a working USB mic (confirmed via `arecord -l` + a raw
arecord/aplay round-trip test) and OPENAI_API_KEY set. LearnX stays
paused, same as the other voice scripts -- this one doesn't touch
Gemini at all.
"""
import asyncio
import audioop  # stdlib; deprecated (PEP 594) but present on 3.11, see
                # pixel_gemini_voice.py's note -- same caveat applies here.
import base64
import json
import logging
import os
import subprocess

import websockets
from dotenv import load_dotenv

import pixel_memory
import pixel_tts  # noqa: F401 -- not used for playback here (aplay direct
                   # via websocket audio deltas), kept for parity/future use.
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
# Confirmed real via GET /v1/models against the actual key, not guessed.
MODEL = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-realtime")
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"

# `arecord -l` to find your mic's card/device, e.g. "plughw:3,0".
CAPTURE_DEVICE = os.environ.get("PIXEL_MIC_DEVICE", "default")
SAMPLE_RATE = 24000  # confirmed required minimum for this API, both directions
SAMPLE_WIDTH = 2  # 16-bit
_CHUNK_MS = 100
_CHUNK_BYTES = int(SAMPLE_RATE * SAMPLE_WIDTH * _CHUNK_MS / 1000)

# Same knobs/defaults as pixel_gemini_voice.py -- watch the "ambient
# level" log line for real numbers from your actual mic/room.
_START_RMS = int(os.environ.get("PIXEL_VAD_START_RMS", "600"))
_END_SILENCE_MS = int(os.environ.get("PIXEL_VAD_SILENCE_MS", "800"))
_MAX_UTTERANCE_MS = 20000
_MIN_UTTERANCE_MS = int(os.environ.get("PIXEL_VAD_MIN_MS", "600"))
_PRE_ROLL_CHUNKS = 3

PERSONA = (
    "You're Pixel, a friendly, casual desk companion robot for a student. "
    "Keep replies short and conversational, like a real spoken chat with "
    "a curious friend, not a lecture. Warm, a little playful, genuinely "
    "interested in what the student says. "
    "Each audio clip may contain more than one thing the student said — "
    "if they change topic or ask something unrelated partway through "
    "(like your name, or a personal question), answer THAT directly "
    "first, don't just keep riding the previous topic's momentum."
)

# Mirrors pixel_memory._SUMMARIZE_PROMPT's contract exactly (one fact per
# line, or NOTHING) -- duplicated as plain text rather than reaching into
# that module's private constant, since this uses a different transport
# (a websocket text turn, not chat.send_message()).
_SUMMARIZE_PROMPT = (
    "Below is a transcript of a casual chat between you (Pixel, a desk "
    "companion robot) and a student. Pull out at most 3 short, durable "
    "facts worth remembering for next time — their name, interests, "
    "ongoing projects, things they mentioned caring about. Skip anything "
    "trivial or one-off (like asking about the weather). One fact per "
    "line, plain text, no numbering or markdown. If there's nothing "
    "worth keeping, reply with exactly: NOTHING\n\n"
    "Transcript:\n{transcript}"
)


def _start_capture() -> subprocess.Popen:
    return subprocess.Popen(
        ["arecord", "-D", CAPTURE_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
         "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )


def _start_playback() -> subprocess.Popen:
    return subprocess.Popen(
        ["aplay", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", "-t", "raw", "-"],
        stdin=subprocess.PIPE,
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


async def _capture_reader(capture_proc: subprocess.Popen, queue: "asyncio.Queue[bytes]") -> None:
    loop = asyncio.get_event_loop()
    while True:
        chunk = await loop.run_in_executor(None, capture_proc.stdout.read, _CHUNK_BYTES)
        if not chunk:
            raise RuntimeError(f"arecord exited unexpectedly (exit code {capture_proc.poll()})")
        await queue.put(chunk)


async def _session_update(ws, instructions: str) -> None:
    await ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "type": "realtime",
            "output_modalities": ["audio"],
            "instructions": instructions,
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                    "turn_detection": None,
                },
                "output": {"format": {"type": "audio/pcm", "rate": SAMPLE_RATE}},
            },
        },
    }))
    ack = json.loads(await ws.recv())
    if ack.get("type") == "error":
        raise RuntimeError(f"session.update rejected: {ack['error']}")


async def _record_and_stream_utterance(
    ws, queue: "asyncio.Queue[bytes]", pixel_speaking: asyncio.Event
) -> int:
    """Same local silence-detection state machine as
    pixel_gemini_voice.py's _record_utterance, but streams chunks to the
    websocket as they're captured instead of buffering a full clip --
    fits this API's append/commit design and avoids holding the whole
    utterance in memory first. Returns the number of chunks sent."""
    loop = asyncio.get_event_loop()
    pre_roll: list[bytes] = []
    recording = False
    silence_ms = 0
    sent_chunks = 0
    ambient_peak = 0
    last_ambient_log = loop.time()

    async def _send(piece: bytes) -> None:
        await ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(piece).decode("ascii"),
        }))

    while True:
        chunk = await queue.get()

        if pixel_speaking.is_set():
            pre_roll.clear()
            continue

        rms = audioop.rms(chunk, SAMPLE_WIDTH)

        if not recording:
            ambient_peak = max(ambient_peak, rms)
            if loop.time() - last_ambient_log >= 2:
                logger.info(
                    "ambient level: current=%d peak=%d (start threshold=%d)",
                    rms, ambient_peak, _START_RMS,
                )
                ambient_peak = 0
                last_ambient_log = loop.time()
            pre_roll.append(chunk)
            if len(pre_roll) > _PRE_ROLL_CHUNKS:
                pre_roll.pop(0)
            if rms >= _START_RMS:
                recording = True
                silence_ms = 0
                for piece in pre_roll:
                    await _send(piece)
                    sent_chunks += 1
            continue

        await _send(chunk)
        sent_chunks += 1
        silence_ms = silence_ms + _CHUNK_MS if rms < _START_RMS else 0

        total_ms = sent_chunks * _CHUNK_MS
        if silence_ms >= _END_SILENCE_MS or total_ms >= _MAX_UTTERANCE_MS:
            return sent_chunks


async def _receive_response(ws, playback_proc: subprocess.Popen, pixel_speaking: asyncio.Event) -> str:
    """Drains events for one response turn: plays audio deltas, collects
    the transcript, returns once response.done arrives."""
    loop = asyncio.get_event_loop()
    transcript = ""
    spoke_any_audio = False
    async for raw in ws:
        data = json.loads(raw)
        t = data.get("type")
        if t == "response.output_audio.delta":
            if not spoke_any_audio:
                face.set_state(STATE_TALKING)
                pixel_speaking.set()
                spoke_any_audio = True
            audio_bytes = base64.b64decode(data["delta"])
            await loop.run_in_executor(None, playback_proc.stdin.write, audio_bytes)
            await loop.run_in_executor(None, playback_proc.stdin.flush)
        elif t == "response.output_audio_transcript.delta":
            transcript += data.get("delta", "")
        elif t == "response.done":
            if spoke_any_audio:
                # Let aplay's buffered tail actually finish before
                # un-muting -- same reasoning as pixel_gemini.py's mute.
                await asyncio.sleep(0.5)
                pixel_speaking.clear()
            return transcript
        elif t == "error":
            raise RuntimeError(f"Realtime API error: {data.get('error')}")
    return transcript


async def _conversation_loop(
    ws, queue: "asyncio.Queue[bytes]", playback_proc: subprocess.Popen,
    pixel_speaking: asyncio.Event, transcript_log: list[str],
) -> None:
    while True:
        face.set_state(STATE_LISTENING)
        sent_chunks = await _record_and_stream_utterance(ws, queue, pixel_speaking)
        utterance_ms = sent_chunks * _CHUNK_MS
        logger.info("utterance captured: %dms of audio", utterance_ms)

        if utterance_ms < _MIN_UTTERANCE_MS:
            logger.info(
                "utterance too short (%dms < %dms) -- discarding, not a real question",
                utterance_ms, _MIN_UTTERANCE_MS,
            )
            await ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
            continue

        face.set_state(STATE_THINKING)
        await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        commit_ack = json.loads(await ws.recv())
        if commit_ack.get("type") == "error":
            logger.error("commit failed: %s", commit_ack.get("error"))
            continue
        await ws.send(json.dumps({"type": "response.create"}))

        reply = await _receive_response(ws, playback_proc, pixel_speaking)
        print(f"Pixel: {reply}")
        transcript_log.append(f"Pixel: {reply}")


async def _summarize_and_remember(transcript_log: list[str]) -> None:
    """OpenAI-specific memory save. pixel_memory.summarize_and_remember
    expects a google-genai chat object, which doesn't apply here -- this
    opens its own short-lived connection for one text-only turn, same
    prompt/parsing contract as the Gemini version."""
    if not transcript_log:
        return
    prompt = _SUMMARIZE_PROMPT.format(transcript="\n".join(transcript_log))
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    try:
        async with websockets.connect(REALTIME_URL, additional_headers=headers) as ws:
            await ws.recv()  # session.created
            await _session_update(ws, "You summarize conversations concisely.")
            await ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": prompt}]},
            }))
            await ws.send(json.dumps({"type": "response.create"}))
            text = ""
            async for raw in ws:
                data = json.loads(raw)
                if data.get("type") == "response.output_audio_transcript.delta":
                    text += data.get("delta", "")
                elif data.get("type") == "response.done":
                    break
    except Exception:
        logger.exception("memory summarization failed")
        return

    if not text or text.strip().upper() == "NOTHING":
        return
    for line in text.splitlines():
        pixel_memory.remember(line)


async def run() -> None:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    system_instruction = PERSONA
    remembered = pixel_memory.load_context()
    if remembered:
        system_instruction = f"{PERSONA}\n\n{remembered}"

    face.start()
    print("Pixel is listening (USB mic, OpenAI Realtime). Ctrl+C to stop.")
    transcript_log: list[str] = []
    try:
        while True:
            capture_proc = _start_capture()
            playback_proc = _start_playback()
            pixel_speaking = asyncio.Event()
            queue: "asyncio.Queue[bytes]" = asyncio.Queue()
            try:
                async with websockets.connect(REALTIME_URL, additional_headers=headers) as ws:
                    await ws.recv()  # session.created
                    await _session_update(ws, system_instruction)
                    await asyncio.gather(
                        _capture_reader(capture_proc, queue),
                        _conversation_loop(ws, queue, playback_proc, pixel_speaking, transcript_log),
                    )
            except Exception:
                logger.exception("Session ended unexpectedly -- reconnecting")
                print("Connection dropped — reconnecting...")
            finally:
                _stop_proc(capture_proc)
                try:
                    playback_proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
                _stop_proc(playback_proc)
            await asyncio.sleep(2)
    finally:
        await _summarize_and_remember(transcript_log)
        face.set_state(STATE_IDLE)
        face.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
