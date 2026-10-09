"""Pixel's voice mode via a fully local LLM (Ollama) + local STT server.

Standalone, new file -- same non-interfering pattern as the other
pixel_*.py mode scripts. Same local-VAD recording approach proven in
pixel_gemini_voice.py (record-until-silence, no server-side VAD to
debug), but a different "brain": instead of one cloud call that
handles both audio understanding and the reply (Gemini's
generateContent), this needs two separate local calls, since
LLaMA 3 / Phi-3 via Ollama are text-only with no built-in audio
understanding at all:
  1. POST the recorded WAV to a local speech-to-text server
     (local_stt_server.py, running on a separate "fast machine" over
     WiFi -- see that file's docstring for setup) -> transcribed text.
  2. POST that text + the running conversation history to Ollama's own
     /api/chat endpoint on the same fast machine -> reply text.

No API costs and no internet dependency once both servers are up --
the tradeoff is reply quality (a local 3-8B model vs GPT-4o/Gemini
class) and needing a separate always-on machine on the same network.
Not yet verified live (no Ollama/STT server available while writing
this) -- syntax-checked and the turn logic exercised with the actual
production functions against a mocked STT/Ollama, but the real
network calls and local-model reply quality still need a hands-on test.

Ollama's /api/chat is stateless per request, unlike Gemini's chat
object which keeps history server-side -- this script keeps its own
`messages` list and resends it every turn, capped at
PIXEL_OLLAMA_MAX_HISTORY entries so a long conversation doesn't make
every turn slower on what's likely a CPU-bound local model.

Requires a working USB mic (same as the other voice scripts) and
PIXEL_STT_URL / PIXEL_OLLAMA_URL pointed at the fast machine. LearnX
and all cloud APIs stay untouched -- this is a fully separate mode.
"""
import asyncio
import audioop  # stdlib; deprecated (PEP 594) but present on 3.11, see
                # pixel_gemini_voice.py's note -- same caveat applies here.
import io
import logging
import os
import subprocess
import wave

import requests
from dotenv import load_dotenv

import pixel_memory
import pixel_tts
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

STT_URL = os.environ["PIXEL_STT_URL"]        # e.g. http://192.168.1.50:5051/transcribe
OLLAMA_URL = os.environ["PIXEL_OLLAMA_URL"]  # e.g. http://192.168.1.50:11434/api/chat
OLLAMA_MODEL = os.environ.get("PIXEL_OLLAMA_MODEL", "llama3")

# `arecord -l` to find your mic's card/device, e.g. "plughw:3,0".
CAPTURE_DEVICE = os.environ.get("PIXEL_MIC_DEVICE", "default")
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit
_CHUNK_MS = 100
_CHUNK_BYTES = int(SAMPLE_RATE * SAMPLE_WIDTH * _CHUNK_MS / 1000)

# Same VAD knobs as pixel_gemini_voice.py/pixel_openai_voice.py -- tune
# per-mic/room, the "ambient level" log line in _record_utterance tells
# you the right PIXEL_VAD_START_RMS for your specific setup.
_START_RMS = int(os.environ.get("PIXEL_VAD_START_RMS", "600"))
_END_SILENCE_MS = int(os.environ.get("PIXEL_VAD_SILENCE_MS", "800"))
_MAX_UTTERANCE_MS = 20000
_MIN_UTTERANCE_MS = int(os.environ.get("PIXEL_VAD_MIN_MS", "600"))
_PRE_ROLL_CHUNKS = 3

_MAX_HISTORY_MESSAGES = int(os.environ.get("PIXEL_OLLAMA_MAX_HISTORY", "20"))

# Same rationale as both OpenAI voice scripts: without one of these,
# memory summarization only fires on Ctrl+C/a crash, never during
# normal continuous use.
_IDLE_TIMEOUT_S = float(os.environ.get("PIXEL_IDLE_TIMEOUT_S", "300"))

# Mirrors pixel_memory._SUMMARIZE_PROMPT's contract exactly (tagged
# CURRENT:/EVENT: lines, or NOTHING) -- duplicated as plain text rather
# than reaching into that module's private constant, same reasoning as
# both OpenAI voice scripts' identical comment.
_SUMMARIZE_PROMPT = (
    "Below is a transcript of a casual chat between you (Pixel, a desk "
    "companion robot) and a student. Pull out at most 3 short, durable "
    "things worth remembering for next time, each tagged as one of two "
    "kinds:\n"
    "CURRENT: a stable fact about the student that should replace any "
    "previous value of the same kind — name, grade, a recurring "
    "interest. Format: CURRENT: key: value (e.g. "
    "'CURRENT: name: Saravana' or 'CURRENT: interests: robotics, "
    "building things').\n"
    "EVENT: something worth carrying forward from this specific "
    "conversation — an unfinished topic to pick back up, something you "
    "(Pixel) promised to follow up on, a running joke or shared moment. "
    "Format: EVENT: <text>.\n"
    "Skip anything trivial or one-off (like asking about the weather). "
    "One tagged item per line, plain text, no numbering or markdown. If "
    "there's nothing worth keeping, reply with exactly: NOTHING\n\n"
    "Transcript:\n{transcript}"
)


class _SessionEnd(Exception):
    """Same pattern as both OpenAI voice scripts -- ends the current
    conversation deliberately (goodbye phrase or idle timeout) so
    run()'s loop knows to save memory and start fresh, distinct from a
    real mic/network error, which should just restart without
    summarizing."""


def _build_persona(name: str) -> str:
    return (
        f"You're {name}, a friendly, casual desk companion robot for a student. "
        "Keep replies short and conversational, like a real spoken chat with "
        "a curious friend, not a lecture. Warm, a little playful, genuinely "
        "interested in what the student says. Plain spoken sentences only — "
        "no markdown, no bullet points, no headings, no LaTeX — this gets "
        "read aloud by a text-to-speech engine that can't pronounce symbols."
    )


def _build_system_instruction() -> str:
    """Reads the current name + memory fresh each time -- so a rename
    detected mid-conversation is picked up correctly, same as both
    OpenAI voice scripts."""
    instruction = _build_persona(pixel_memory.load_name())
    remembered = pixel_memory.load_context()
    if remembered:
        instruction = f"{instruction}\n\n{remembered}"
    return instruction


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
    loop = asyncio.get_event_loop()
    while True:
        chunk = await loop.run_in_executor(None, capture_proc.stdout.read, _CHUNK_BYTES)
        if not chunk:
            raise RuntimeError(f"arecord exited unexpectedly (exit code {capture_proc.poll()})")
        await queue.put(chunk)


async def _record_utterance(
    queue: "asyncio.Queue[bytes]", pixel_speaking: asyncio.Event, last_activity: dict
) -> bytes:
    """Same local silence-detection state machine as
    pixel_gemini_voice.py's _record_utterance."""
    loop = asyncio.get_event_loop()
    pre_roll: list[bytes] = []
    buffer: list[bytes] = []
    recording = False
    silence_ms = 0
    ambient_peak = 0
    last_ambient_log = loop.time()

    while True:
        chunk = await queue.get()
        if pixel_speaking.is_set():
            pre_roll.clear()
            continue

        rms = audioop.rms(chunk, SAMPLE_WIDTH)

        if not recording:
            ambient_peak = max(ambient_peak, rms)
            if loop.time() - last_ambient_log >= 2:
                logger.info("ambient level: current=%d peak=%d (start threshold=%d)",
                            rms, ambient_peak, _START_RMS)
                ambient_peak = 0
                last_ambient_log = loop.time()
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
            last_activity["at"] = loop.time()
            return b"".join(buffer)


async def _idle_watchdog(last_activity: dict) -> None:
    loop = asyncio.get_event_loop()
    while True:
        await asyncio.sleep(10)
        if loop.time() - last_activity["at"] >= _IDLE_TIMEOUT_S:
            raise _SessionEnd("idle timeout")


async def _speak(text: str, pixel_speaking: asyncio.Event) -> None:
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


def _transcribe(wav_bytes: bytes) -> str:
    resp = requests.post(STT_URL, data=wav_bytes,
                          headers={"Content-Type": "audio/wav"}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("text", "").strip()


def _ollama_chat(messages: list[dict]) -> str:
    resp = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }, timeout=60)
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "").strip()


async def _conversation_loop(
    queue: "asyncio.Queue[bytes]", pixel_speaking: asyncio.Event,
    messages: list[dict], transcript_log: list[str], last_activity: dict,
) -> None:
    loop = asyncio.get_event_loop()
    while True:
        face.set_state(STATE_LISTENING)
        audio_bytes = await _record_utterance(queue, pixel_speaking, last_activity)
        utterance_ms = len(audio_bytes) / (SAMPLE_RATE * SAMPLE_WIDTH) * 1000
        logger.info("utterance captured: %.0fms of audio", utterance_ms)
        if utterance_ms < _MIN_UTTERANCE_MS:
            logger.info("utterance too short (%.0fms < %dms) -- discarding, not a real question",
                        utterance_ms, _MIN_UTTERANCE_MS)
            continue

        face.set_state(STATE_THINKING)
        wav_bytes = _pcm_to_wav(audio_bytes)
        try:
            user_text = await loop.run_in_executor(None, _transcribe, wav_bytes)
        except Exception:
            logger.exception("STT request failed")
            continue
        if not user_text:
            logger.info("STT returned empty text -- discarding")
            continue

        print(f"You: {user_text}")
        transcript_log.append(f"Student: {user_text}")
        new_name = pixel_memory.detect_rename_request(user_text)
        if new_name:
            pixel_memory.set_name(new_name)
            print(f"(Pixel's name is now {new_name})")
            # Unlike the OpenAI scripts, this takes effect starting
            # with THIS turn's reply, not the next one -- messages[0]
            # is plain local state, not a server-side session, so
            # updating it before the chat call below already changes
            # what the model sees for the current request.
            messages[0] = {"role": "system", "content": _build_system_instruction()}
        is_goodbye = pixel_memory.detect_goodbye(user_text)

        messages.append({"role": "user", "content": user_text})
        del messages[1:-_MAX_HISTORY_MESSAGES]  # keep system message + last N turns

        try:
            reply = await loop.run_in_executor(None, _ollama_chat, messages)
        except Exception:
            logger.exception("Ollama request failed")
            messages.pop()  # don't leave an unanswered turn in history
            continue
        if not reply:
            messages.pop()
            continue
        messages.append({"role": "assistant", "content": reply})

        print(f"Pixel: {reply}")
        transcript_log.append(f"Pixel: {reply}")
        face.set_state(STATE_TALKING)
        await _speak(reply, pixel_speaking)

        if is_goodbye:
            # Raised only after _speak() above returns, i.e. after the
            # farewell reply has fully played -- same reasoning as both
            # OpenAI voice scripts' goodbye handling.
            raise _SessionEnd("goodbye detected")


async def _summarize_and_remember(transcript_log: list[str]) -> None:
    if not transcript_log:
        return
    pixel_memory.save_transcript(transcript_log)
    prompt = _SUMMARIZE_PROMPT.format(transcript="\n".join(transcript_log))
    loop = asyncio.get_event_loop()
    try:
        text = await loop.run_in_executor(
            None, _ollama_chat, [{"role": "user", "content": prompt}])
    except Exception:
        logger.exception("memory summarization failed")
        return
    pixel_memory.apply_summary(text)


async def run() -> None:
    face.start()
    print(f"{pixel_memory.load_name()} is listening (USB mic, local Ollama "
          f"model={OLLAMA_MODEL}, idle timeout {_IDLE_TIMEOUT_S:.0f}s). "
          f"Say goodbye or Ctrl+C to end a conversation.")
    transcript_log: list[str] = []
    try:
        while True:
            messages: list[dict] = [{"role": "system", "content": _build_system_instruction()}]
            capture_proc = _start_capture()
            pixel_speaking = asyncio.Event()
            queue: "asyncio.Queue[bytes]" = asyncio.Queue()
            last_activity = {"at": asyncio.get_event_loop().time()}
            try:
                await asyncio.gather(
                    _capture_reader(capture_proc, queue),
                    _conversation_loop(queue, pixel_speaking, messages, transcript_log, last_activity),
                    _idle_watchdog(last_activity),
                )
            except _SessionEnd as e:
                print(f"(ending conversation: {e} -- saving memory)")
                await _summarize_and_remember(transcript_log)
                transcript_log.clear()
            except Exception:
                logger.exception("Mic capture failed -- restarting")
                print("Mic capture dropped — restarting...")
            finally:
                _stop_proc(capture_proc)
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
