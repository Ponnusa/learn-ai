"""Pixel's voice mode via OpenAI's Realtime API, using SERVER-side semantic VAD.

Standalone, new file -- experimental sibling to pixel_openai_voice.py,
which deliberately disables server turn detection (turn_detection: null)
in favor of a local silence-detection state machine. This file is the
opposite choice: it trusts the server's own semantic VAD to decide turn
boundaries, after live-testing showed it's not the same trap Gemini's
server VAD was.

Architecturally this is NOT just a config change from
pixel_openai_voice.py -- enabling server-side turn detection means the
server decides when a turn starts/ends and auto-triggers responses, so
the send loop has to continuously stream raw audio (gated only by the
no-AEC mute, not by local amplitude thresholds) and the receive loop has
to react to input_audio_buffer.speech_started/speech_stopped events
instead of calling .commit()/response.create() ourselves. Closer in
shape to pixel_gemini.py's Live-API loop than to
pixel_openai_voice.py's turn-based one.

Verified live before writing this, specifically to avoid repeating the
Gemini Live mistake of trusting server VAD blind:
  - turn_detection: {"type": "semantic_vad", "eagerness": "low"} and
    "medium" were tested with real synthesized speech (two separate
    utterances in one session) and never cleanly completed a second
    turn within a 90s window -- "low" never got past speech_started at
    all for either eagerness in an earlier pure-tone test (semantic VAD
    needs actual linguistic content, not just loud audio, confirmed by
    it firing nothing for a sine tone but firing speech_started for real
    TTS speech); "medium" completed turn 1 cleanly but turn 2 produced
    an empty response.done with speech_stopped/committed/response.created
    all missing -- a flaky race, not a clean failure.
  - eagerness: "high" completed TWO full, correct multi-turn cycles in
    the same session, twice over (repeated the test) -- speech_started,
    speech_stopped, committed, response.created, response.done, correct
    transcript, every time. That's the one actually used here. The
    tradeoff: "high" is less patient about natural mid-sentence pauses
    than low/medium would be if they worked -- closer to simple
    energy-based VAD with some semantic awareness layered in, not the
    "waits through thoughtful pauses" behavior that made semantic VAD
    interesting in the first place.

Same session/audio/event-name facts already verified for
pixel_openai_voice.py apply here unchanged (GA wire format, 24kHz both
directions, response.output_audio.delta naming, etc.) -- see that file's
docstring for those citations, not repeated here.

Requires a working USB mic and OPENAI_API_KEY set. LearnX stays paused.
"""
import asyncio
import audioop  # stdlib; deprecated (PEP 594) but present on 3.11.
import base64
import io
import json
import logging
import os
import subprocess
import wave
from datetime import datetime

import websockets
from dotenv import load_dotenv

import pixel_memory
from pixel_face import face, STATE_IDLE, STATE_LISTENING, STATE_THINKING, STATE_TALKING

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
MODEL = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-realtime")
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"

CAPTURE_DEVICE = os.environ.get("PIXEL_MIC_DEVICE", "default")
SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2
_CHUNK_MS = 100
_CHUNK_BYTES = int(SAMPLE_RATE * SAMPLE_WIDTH * _CHUNK_MS / 1000)

# The ONLY semantic_vad setting confirmed to survive multiple turns
# cleanly in live testing -- see module docstring. Don't change this to
# "low"/"medium" without re-verifying the same way; both showed real
# problems, not just slowness.
EAGERNESS = os.environ.get("PIXEL_SEMANTIC_VAD_EAGERNESS", "high")

AUDIO_LOG_DIR = os.environ.get("PIXEL_AUDIO_LOG_DIR")

# Without one of these, memory summarization only ever fires on
# Ctrl+C/a crash -- run()'s outer loop reconnects on every other
# Exception, so it never fires during normal continuous operation.
_IDLE_TIMEOUT_S = float(os.environ.get("PIXEL_IDLE_TIMEOUT_S", "300"))


class _SessionEnd(Exception):
    """Raised to deliberately end the current conversation (goodbye
    phrase detected, or idle timeout) so run()'s outer loop can save
    memory and start a fresh one -- distinct from a real connection
    error, which should just reconnect without summarizing."""


async def _idle_watchdog(last_activity: dict) -> None:
    """Fallback for when the student just walks away without saying
    goodbye. Runs alongside the other loops in asyncio.gather()."""
    loop = asyncio.get_event_loop()
    while True:
        await asyncio.sleep(10)
        if loop.time() - last_activity["at"] >= _IDLE_TIMEOUT_S:
            raise _SessionEnd("idle timeout")


def _build_persona(name: str) -> str:
    return (
        f"You're {name}, a friendly, casual desk companion robot for a student. "
        "Keep replies short and conversational, like a real spoken chat with "
        "a curious friend, not a lecture. Warm, a little playful, genuinely "
        "interested in what the student says. "
        "Each audio clip may contain more than one thing the student said — "
        "if they change topic or ask something unrelated partway through "
        "(like your name, or a personal question), answer THAT directly "
        "first, don't just keep riding the previous topic's momentum."
    )


def _build_system_instruction() -> str:
    """Reads the current name + memory fresh each time -- so a rename
    detected mid-session is picked up correctly even across a reconnect,
    not just at startup."""
    instruction = _build_persona(pixel_memory.load_name())
    remembered = pixel_memory.load_context()
    if remembered:
        instruction = f"{instruction}\n\n{remembered}"
    return instruction

# Mirrors pixel_memory._SUMMARIZE_PROMPT's contract exactly (tagged
# CURRENT:/EVENT: lines, or NOTHING) -- see pixel_openai_voice.py's
# identical comment for why the prompt text is duplicated but the
# parsing (apply_summary) and transcript saving (save_transcript) are
# shared via pixel_memory.
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


def _start_capture() -> subprocess.Popen:
    return subprocess.Popen(
        ["arecord", "-D", CAPTURE_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
         "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
    )


def _start_playback() -> subprocess.Popen:
    return subprocess.Popen(
        ["aplay", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", "-t", "raw",
         "-B", "500000", "-"],
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


def _pcm_to_wav(pcm_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def _log_utterance(audio_bytes: bytes, reply_text: str) -> None:
    if not AUDIO_LOG_DIR or not audio_bytes:
        return
    try:
        os.makedirs(AUDIO_LOG_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        wav_name = f"{timestamp}.wav"
        with open(os.path.join(AUDIO_LOG_DIR, wav_name), "wb") as f:
            f.write(_pcm_to_wav(audio_bytes))
        with open(os.path.join(AUDIO_LOG_DIR, "session_log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": timestamp,
                "audio_file": wav_name,
                "utterance_ms": round(len(audio_bytes) / (SAMPLE_RATE * SAMPLE_WIDTH) * 1000),
                "reply": reply_text,
            }) + "\n")
    except OSError:
        logger.exception("failed to write audio log entry")


async def _capture_reader(capture_proc: subprocess.Popen, queue: "asyncio.Queue[bytes]") -> None:
    loop = asyncio.get_event_loop()
    while True:
        chunk = await loop.run_in_executor(None, capture_proc.stdout.read, _CHUNK_BYTES)
        if not chunk:
            raise RuntimeError(f"arecord exited unexpectedly (exit code {capture_proc.poll()})")
        await queue.put(chunk)


def _build_session_dict(
    instructions: str, modalities: tuple[str, ...] = ("audio",),
    max_output_tokens: int | None = 600, use_semantic_vad: bool = True,
) -> dict:
    session: dict = {
        "type": "realtime",
        "output_modalities": modalities,
        "instructions": instructions,
    }
    if max_output_tokens is not None:
        session["max_output_tokens"] = max_output_tokens
    if "audio" in modalities:
        session["audio"] = {
            "input": {
                "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                "turn_detection": (
                    {
                        "type": "semantic_vad",
                        "eagerness": EAGERNESS,
                        "create_response": True,
                        "interrupt_response": True,
                    }
                    if use_semantic_vad else None
                ),
                # Without this, transcript_log only ever contained
                # Pixel's own replies, never what the student actually
                # said -- confirmed live: conversation.item.input_audio_
                # transcription.completed gives an accurate transcript.
                "transcription": {"model": "whisper-1"},
            },
            "output": {"format": {"type": "audio/pcm", "rate": SAMPLE_RATE}},
        }
    return session


async def _session_update(
    ws, instructions: str, modalities: tuple[str, ...] = ("audio",),
    max_output_tokens: int | None = 600, use_semantic_vad: bool = True,
) -> None:
    session = _build_session_dict(instructions, modalities, max_output_tokens, use_semantic_vad)
    await ws.send(json.dumps({"type": "session.update", "session": session}))
    ack = json.loads(await ws.recv())
    if ack.get("type") == "error":
        raise RuntimeError(f"session.update rejected: {ack['error']}")


async def _send_session_update_no_wait(ws, instructions: str) -> None:
    """Like _session_update, but doesn't consume a reply -- for use from
    inside _receive_loop's own async-for, where a nested ws.recv() could
    steal a message meant for the main loop's next iteration (_send_loop
    is also sending concurrently on the same connection). The
    session.updated ack (or an error) just flows through as an ordinary,
    currently-unhandled event on the next iteration instead."""
    session = _build_session_dict(instructions)
    await ws.send(json.dumps({"type": "session.update", "session": session}))


def _encode_append_message(chunk: bytes) -> str:
    return json.dumps({
        "type": "input_audio_buffer.append",
        "audio": base64.b64encode(chunk).decode("ascii"),
    })


def _decode_and_play(playback_proc: subprocess.Popen, b64_audio: str) -> int:
    """Decode + write + flush in one executor dispatch instead of three
    separate ones (decode was inline before; write/flush were already
    offloaded but as two separate calls) -- fewer thread-pool round
    trips per audio delta, which arrive frequently during playback.
    Returns the decoded byte count so the caller can track how much
    audio has actually been queued for playback."""
    audio_bytes = base64.b64decode(b64_audio)
    playback_proc.stdin.write(audio_bytes)
    playback_proc.stdin.flush()
    return len(audio_bytes)


async def _send_loop(
    ws, queue: "asyncio.Queue[bytes]", pixel_speaking: asyncio.Event, recording_state: dict
) -> None:
    """Continuously forwards captured mic audio -- no local amplitude
    gating; the server's semantic_vad decides turn boundaries itself.
    Still muted while Pixel is speaking: no AEC on this hardware, and
    with interrupt_response enabled, unmuted echo could make the server
    think the user is barging in on Pixel's own voice."""
    loop = asyncio.get_event_loop()
    chunks_sent = 0
    last_heartbeat = loop.time()
    while True:
        chunk = await queue.get()
        if pixel_speaking.is_set():
            continue
        # base64-encoding + json.dumps were running inline on the event
        # loop every ~100ms, forever -- on a single weak core, that's
        # exactly the kind of blocking that starves aplay's buffer into
        # an underrun. Offloading to a thread lets the loop keep
        # servicing the playback write path while this runs.
        message = await loop.run_in_executor(None, _encode_append_message, chunk)
        await ws.send(message)
        if recording_state["active"]:
            recording_state["buffer"].append(chunk)
        chunks_sent += 1
        if loop.time() - last_heartbeat >= 5:
            logger.info("mic send alive: %d chunks sent so far", chunks_sent)
            last_heartbeat = loop.time()


async def _receive_loop(
    ws, playback_proc: subprocess.Popen, pixel_speaking: asyncio.Event,
    transcript_log: list[str], recording_state: dict, last_activity: dict,
) -> None:
    loop = asyncio.get_event_loop()
    transcript = ""
    user_transcript = ""
    spoke_any_audio = False
    audio_bytes_total = 0
    playback_started_at = 0.0
    async for raw in ws:
        # Also offloaded -- parsing every incoming message inline was
        # part of the same event-loop contention causing the underruns.
        data = await loop.run_in_executor(None, json.loads, raw)
        t = data.get("type")

        if t == "input_audio_buffer.speech_started":
            face.set_state(STATE_LISTENING)
            recording_state["active"] = True
            recording_state["buffer"] = []
            last_activity["at"] = loop.time()
        elif t == "input_audio_buffer.speech_stopped":
            face.set_state(STATE_THINKING)
            recording_state["active"] = False
            recording_state["last_buffer"] = b"".join(recording_state["buffer"])
        elif t == "conversation.item.input_audio_transcription.completed":
            # Without this, transcript_log only ever had Pixel's own
            # replies -- memory extraction was blind to what the student
            # actually said. Confirmed live this fires before response.done.
            user_transcript = data.get("transcript", "")
        elif t == "response.output_audio.delta":
            if not spoke_any_audio:
                face.set_state(STATE_TALKING)
                pixel_speaking.set()
                spoke_any_audio = True
                audio_bytes_total = 0
                playback_started_at = loop.time()
            audio_bytes_total += await loop.run_in_executor(
                None, _decode_and_play, playback_proc, data["delta"])
        elif t == "response.output_audio_transcript.delta":
            transcript += data.get("delta", "")
        elif t == "response.done":
            last_activity["at"] = loop.time()
            is_goodbye = bool(user_transcript) and pixel_memory.detect_goodbye(user_transcript)
            if user_transcript:
                print(f"You: {user_transcript}")
                transcript_log.append(f"Student: {user_transcript}")
                new_name = pixel_memory.detect_rename_request(user_transcript)
                if new_name:
                    pixel_memory.set_name(new_name)
                    print(f"(Pixel's name is now {new_name})")
                    # Takes effect starting next turn, not this one --
                    # the server already auto-triggered this turn's
                    # response before we could see this transcript.
                    await _send_session_update_no_wait(ws, _build_system_instruction())
            if transcript:
                print(f"Pixel: {transcript}")
                transcript_log.append(f"Pixel: {transcript}")
                _log_utterance(recording_state.get("last_buffer", b""), transcript)
            transcript = ""
            user_transcript = ""
            if spoke_any_audio:
                # A flat 0.5s guess here let Pixel's own trailing audio
                # (still draining through the OS pipe + aplay's ALSA
                # buffer, not bounded tightly by -B 500000) get picked
                # back up by the mic and misread as the student's next
                # turn -- confirmed via a real session log showing
                # Pixel's own phrases echoed back verbatim as "Student:"
                # lines. Wait out the reply's actual decoded duration
                # (minus whatever's already elapsed since playback
                # started, since deltas don't always arrive in real
                # time) plus a fixed drain margin, instead of a fixed
                # guess that doesn't scale with reply length.
                expected_s = audio_bytes_total / (SAMPLE_RATE * SAMPLE_WIDTH)
                elapsed = loop.time() - playback_started_at
                await asyncio.sleep(max(0.0, expected_s - elapsed) + 0.6)
                pixel_speaking.clear()
            spoke_any_audio = False
            face.set_state(STATE_LISTENING)
            if is_goodbye:
                # Raised only after the farewell reply has fully played
                # (the unmute wait above already happened) -- run()'s
                # outer loop catches this specifically to save memory
                # and start a fresh conversation, instead of treating
                # it as a dropped connection.
                raise _SessionEnd("goodbye detected")
        elif t == "error":
            raise RuntimeError(f"Realtime API error: {data.get('error')}")


async def _summarize_and_remember(transcript_log: list[str]) -> None:
    if not transcript_log:
        return
    pixel_memory.save_transcript(transcript_log)
    prompt = _SUMMARIZE_PROMPT.format(transcript="\n".join(transcript_log))
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    try:
        async with websockets.connect(REALTIME_URL, additional_headers=headers) as ws:
            await ws.recv()
            await _session_update(
                ws, "You summarize conversations concisely.",
                modalities=("text",), use_semantic_vad=False,
            )
            await ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": prompt}]},
            }))
            await ws.send(json.dumps({"type": "response.create"}))
            text = ""
            async for raw in ws:
                data = json.loads(raw)
                if data.get("type") == "response.output_text.delta":
                    text += data.get("delta", "")
                elif data.get("type") == "response.done":
                    break
    except Exception:
        logger.exception("memory summarization failed")
        return

    pixel_memory.apply_summary(text)


async def run() -> None:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    face.start()
    print(f"{pixel_memory.load_name()} is listening (USB mic, OpenAI Realtime, "
          f"semantic_vad eagerness={EAGERNESS}, idle timeout {_IDLE_TIMEOUT_S:.0f}s). "
          f"Say goodbye or Ctrl+C to end a conversation.")
    transcript_log: list[str] = []
    try:
        while True:
            system_instruction = _build_system_instruction()
            capture_proc = _start_capture()
            playback_proc = _start_playback()
            pixel_speaking = asyncio.Event()
            queue: "asyncio.Queue[bytes]" = asyncio.Queue()
            recording_state = {"active": False, "buffer": [], "last_buffer": b""}
            last_activity = {"at": asyncio.get_event_loop().time()}
            try:
                async with websockets.connect(REALTIME_URL, additional_headers=headers) as ws:
                    await ws.recv()  # session.created
                    await _session_update(ws, system_instruction)
                    await asyncio.gather(
                        _capture_reader(capture_proc, queue),
                        _send_loop(ws, queue, pixel_speaking, recording_state),
                        _receive_loop(ws, playback_proc, pixel_speaking, transcript_log, recording_state, last_activity),
                        _idle_watchdog(last_activity),
                    )
            except _SessionEnd as e:
                print(f"(ending conversation: {e} -- saving memory)")
                await _summarize_and_remember(transcript_log)
                transcript_log.clear()
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
