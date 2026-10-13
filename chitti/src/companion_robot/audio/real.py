"""Real AudioTransport using a single persistent aplay subprocess for
playback, kept open across the whole session rather than reopened for
every reply.

Fixes a real bug found live on the Pi: a cheap USB audio device needs
a moment to "wake up" each time its ALSA device is freshly opened --
the first version here spawned a brand new `aplay` (and device open)
for every single reply, which silently swallowed the start of short
clips ("Goodbye! Have a great day!" came out as just "day"). Every
mature pixel-ai voice script (pixel_openai_voice_semantic.py,
pixel_gemini.py, pixel_ollama_voice.py) already settled on exactly
this fix for this same class of hardware: one `playback_proc` per
session, written to repeatedly via its stdin pipe, never respawned
between utterances.

Expects raw PCM audio with no WAV header, 16-bit signed LE mono at
PLAYBACK_SAMPLE_RATE -- matching OpenAITTSBackend's
response_format="pcm" request exactly, the same raw-stream convention
pixel-ai's own `aplay -t raw` calls use.

play() blocks until the written audio has actually finished playing.
There's no WAV header to read a duration from and no direct "done
playing" signal from a stdin-piped aplay, so this is computed from the
byte count plus a short grace period for ALSA's own internal buffer
(-B 500000 = 500ms) to drain -- same reasoning as
pixel-ai/pixel_gemini.py's documented "give any already-queued tail a
moment to actually finish" wait.

A first version slept for the *full* computed duration after the write
call returned, on top of whatever the write call itself already
blocked for. That double-counts: the OS pipe (commonly ~64KB, under
2 seconds of this audio format) fills up during the write for any clip
longer than that, so `stdin.write()` already blocks close to real-time
once aplay can only drain it as fast as actual playback consumes it.
Found live: a multi-sentence story took roughly double its real length
to finish playing, long enough that the next steps (writing the
Story-Companion memory record, prompting for the next turn) looked
like the program had hung -- it just hadn't gotten there yet. Fixed by
timing the write itself and only sleeping for whatever's left of the
expected duration, so a short clip (write returns almost instantly,
fits inside the pipe buffer) still waits close to its full duration,
and a long clip (write already blocked near real-time) doesn't wait
again for the same time twice.

CAPTURE_DEVICE/PLAYBACK_DEVICE: pixel-ai's own README documents real
hardware experience that ALSA's "default" device often does NOT route
to the actual USB mic/speaker on this hardware -- every one of its
voice scripts sets PIXEL_MIC_DEVICE/PIXEL_SPEAKER_DEVICE explicitly
(e.g. "plughw:1,0", found via `arecord -l`/`aplay -l`) rather than
relying on "default". Same real constraint applies here, so the same
override is exposed -- under chitti's own env var names, not pixel-ai's,
since the two projects' configs are otherwise fully independent
(decision 0001), even though it's the same physical device and likely
the same value. voice_loop_demo.py's capture helper imports
CAPTURE_DEVICE from here rather than duplicating this env-var read.

capture_chunks() is NOT implemented as true continuous streaming here.
That's real Milestone 2 scope once wake-word/VAD exists -- this device
has neither yet (openWakeWord needs an ARMv6 wheel that doesn't exist;
see docs/decisions/0016). This transport is built for the push-to-talk
demo in voice_loop_demo.py, which records a bounded clip between two
keypresses via its own helper, not through this interface's streaming
method.
"""
import asyncio
import os
import subprocess
import time
from collections.abc import AsyncIterator

# Import triggers config.loader's load_dotenv() before the env vars
# below are read -- this file reads them at import time, and without
# this, importing audio.real before anything else that happens to
# import config.loader (e.g. being the first import in
# voice_loop_demo.py) would silently read CHITTI_MIC_DEVICE/
# CHITTI_SPEAKER_DEVICE as unset, falling back to "default" even with
# a real value in .env. The exact same class of bug already hit once
# in pixel-ai (pixel_direct_llm.py missing its own load_dotenv()) --
# confirmed again here live: a real-hardware test recorded from the
# wrong device because of this, caught via Whisper transcribing "you"
# (its classic near-silence hallucination) instead of real speech.
import companion_robot.config.loader  # noqa: F401

from .interfaces import AudioTransport

CAPTURE_DEVICE = os.environ.get("CHITTI_MIC_DEVICE", "default")
PLAYBACK_DEVICE = os.environ.get("CHITTI_SPEAKER_DEVICE", "default")
PLAYBACK_SAMPLE_RATE = 24000  # must match OpenAITTSBackend's PCM output rate
_BYTES_PER_SAMPLE = 2  # 16-bit signed LE, mono
_BUFFER_DRAIN_GRACE_SECONDS = 0.6  # a bit more than -B 500000's 500ms


class RealAudioTransport(AudioTransport):
    def __init__(self) -> None:
        self._playback_proc: subprocess.Popen | None = None

    def _ensure_playback_proc(self) -> subprocess.Popen:
        if self._playback_proc is not None and self._playback_proc.poll() is None:
            return self._playback_proc
        self._playback_proc = subprocess.Popen(
            [
                "aplay", "-D", PLAYBACK_DEVICE,
                "-f", "S16_LE", "-r", str(PLAYBACK_SAMPLE_RATE), "-c", "1",
                "-t", "raw", "-B", "500000", "-q", "-",
            ],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return self._playback_proc

    async def capture_chunks(self) -> AsyncIterator[bytes]:
        raise NotImplementedError(
            "Continuous streaming capture isn't built for this push-to-talk "
            "demo -- see voice_loop_demo.py's record_clip() for the bounded-"
            "clip recording this transport is actually paired with."
        )
        yield b""  # pragma: no cover -- unreachable, keeps this an async generator

    async def play(self, audio: bytes) -> None:
        proc = self._ensure_playback_proc()
        expected_duration = len(audio) / (PLAYBACK_SAMPLE_RATE * _BYTES_PER_SAMPLE)
        write_started_at = time.monotonic()
        await asyncio.get_event_loop().run_in_executor(None, self._write, proc, audio)
        write_elapsed = time.monotonic() - write_started_at
        remaining = max(0.0, expected_duration - write_elapsed) + _BUFFER_DRAIN_GRACE_SECONDS
        await asyncio.sleep(remaining)

    def _write(self, proc: subprocess.Popen, audio: bytes) -> None:
        proc.stdin.write(audio)
        proc.stdin.flush()

    async def stop_playback(self) -> None:
        # Barge-in: kills the persistent process outright so any
        # queued/buffered audio stops immediately. Not currently called
        # anywhere in voice_loop_demo.py's turn-based flow (no barge-in
        # built for this demo), but note for whoever adds it later: the
        # next play() call after this will pay the device-warmup cost
        # again, since _ensure_playback_proc() has to spawn a fresh one.
        if self._playback_proc is None or self._playback_proc.poll() is not None:
            return
        self._playback_proc.terminate()
        try:
            self._playback_proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self._playback_proc.kill()
        self._playback_proc = None

    def is_muted(self) -> bool:
        return False  # no physical mute switch on this device yet
