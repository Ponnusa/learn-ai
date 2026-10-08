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
import logging
import os
import subprocess

from dotenv import load_dotenv
from google import genai
from google.genai import types

from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_TALKING

# %(asctime)s was missing before -- made it impossible to tell from a
# pasted log how long a "stuck" gap actually lasted, or whether anything
# was still happening during it.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

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
    # stderr NOT suppressed here (unlike most other subprocess calls in
    # this codebase) -- arecord dying silently with its real ALSA error
    # swallowed is exactly what produced "nothing happens, no crash" when
    # it stopped producing audio after the first exchange. Let it print.
    return subprocess.Popen(
        ["arecord", "-D", CAPTURE_DEVICE, "-f", "S16_LE", "-r", str(SEND_RATE),
         "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )


def _start_playback() -> subprocess.Popen:
    return subprocess.Popen(
        ["aplay", "-f", "S16_LE", "-r", str(RECEIVE_RATE), "-c", "1", "-t", "raw", "-"],
        stdin=subprocess.PIPE,
    )


async def _send_mic_audio(
    session, capture_proc: subprocess.Popen, pixel_speaking: asyncio.Event
) -> None:
    loop = asyncio.get_event_loop()
    chunks_read = 0
    chunks_sent = 0
    chunks_muted = 0
    last_heartbeat = loop.time()
    while True:
        chunk = await loop.run_in_executor(None, capture_proc.stdout.read, _CHUNK_BYTES)
        if not chunk:
            # arecord exited (EOF on its stdout) -- treat this as a real
            # failure rather than quietly ending this coroutine while
            # _receive_and_play keeps waiting forever with no new input
            # ever arriving. Raising here lets run()'s reconnect loop
            # catch it, log the real cause, and restart capture/playback.
            raise RuntimeError(
                f"arecord exited unexpectedly (exit code {capture_proc.poll()})"
            )
        chunks_read += 1
        # No acoustic echo cancellation on this hardware -- the webcam
        # mic picks up Pixel's own voice straight out of the speaker.
        # Fed back into the session, that looks like new "user speech"
        # and confuses the server's turn detection: exactly one good
        # reply per session, then permanent silence, matched what kept
        # showing up in testing. Simplest fix without real AEC: don't
        # forward mic audio while Pixel is speaking. Still read and
        # discard it (not skipping the read itself) so arecord's buffer
        # doesn't back up while muted.
        if pixel_speaking.is_set():
            chunks_muted += 1
        else:
            await session.send_realtime_input(
                audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={SEND_RATE}")
            )
            chunks_sent += 1
        # One line every ~5s, not every chunk (10/s would be spam). This
        # used to log chunks_read mislabeled as "sent" even while muted
        # -- fixed to report real counts, since that was masking exactly
        # the kind of bug (mute stuck on, nothing actually reaching
        # Gemini) this is meant to rule out.
        if loop.time() - last_heartbeat >= 5:
            logger.info(
                "mic: %d read, %d actually sent, %d muted so far",
                chunks_read, chunks_sent, chunks_muted,
            )
            last_heartbeat = loop.time()


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


def _write_audio(playback_proc: subprocess.Popen, audio_bytes: bytes) -> None:
    playback_proc.stdin.write(audio_bytes)
    playback_proc.stdin.flush()


async def _receive_and_play(
    session, playback_proc: subprocess.Popen, pixel_speaking: asyncio.Event
) -> None:
    loop = asyncio.get_event_loop()
    async for response in session.receive():
        audio_bytes = _extract_audio(response)
        if audio_bytes:
            face.set_state(STATE_TALKING)
            pixel_speaking.set()
            # Writing directly here (no executor) blocks the WHOLE
            # asyncio event loop if aplay's pipe buffer fills or the
            # ALSA device is slow -- which also stalls the websocket
            # library's background keepalive-ping handling, and that's
            # exactly what was producing "keepalive ping timeout"
            # disconnects right after the first real audio reply.
            await loop.run_in_executor(None, _write_audio, playback_proc, audio_bytes)
        if _is_turn_complete(response):
            # aplay buffers what we've already written -- give any
            # already-queued tail a moment to actually finish playing
            # before un-muting the mic, or its last fraction of a second
            # could still leak back in as "new" input.
            await asyncio.sleep(0.5)
            pixel_speaking.clear()
            face.set_state(STATE_LISTENING)
            logger.info("turn complete -- listening again")


def _stop_proc(proc: subprocess.Popen | None, timeout: float = 2) -> None:
    """terminate() alone doesn't block until the process (and whatever
    hardware it's holding, e.g. the USB mic device) is actually released
    -- that gap was exactly why every reconnect after the first failed
    with "Device or resource busy": a new arecord kept starting before
    the old one had actually let go of the device."""
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


async def run() -> None:
    client = genai.Client(api_key=GEMINI_API_KEY)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=PERSONA,
        # Reported symptom: continuous mic audio was reaching Gemini
        # fine (confirmed via the heartbeat log), but it took ~15-20s of
        # talking before any reply came back -- server-side VAD waiting
        # out a long silence window before deciding you'd finished
        # speaking. Explicit, aggressive settings instead of relying on
        # defaults: react to speech starting/ending quickly, and commit
        # to "done speaking" after a short 400ms pause instead of
        # whatever the default silence window actually is.
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                prefix_padding_ms=200,
                silence_duration_ms=400,
            )
        ),
    )

    face.start()
    print("Pixel is listening (USB headset). Ctrl+C to stop.")
    try:
        while True:
            capture_proc = _start_capture()
            playback_proc = _start_playback()
            pixel_speaking = asyncio.Event()
            face.set_state(STATE_LISTENING)
            try:
                async with client.aio.live.connect(model=MODEL, config=config) as session:
                    await asyncio.gather(
                        _send_mic_audio(session, capture_proc, pixel_speaking),
                        _receive_and_play(session, playback_proc, pixel_speaking),
                    )
            except Exception:
                # The Live session can close on its own (idle timeout,
                # server hiccup, etc.) -- logged in full here so the real
                # cause is visible next time, instead of the whole script
                # just going silent/dying. Reconnect rather than give up.
                logger.exception("Live session ended unexpectedly -- reconnecting")
                print("Connection dropped — reconnecting...")
            finally:
                _stop_proc(capture_proc)
                try:
                    playback_proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
                _stop_proc(playback_proc)
            # Extra grace period beyond the process actually exiting --
            # some USB audio drivers release the device a beat slower
            # than the process itself exits.
            await asyncio.sleep(2)
    finally:
        face.set_state(STATE_IDLE)
        face.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
