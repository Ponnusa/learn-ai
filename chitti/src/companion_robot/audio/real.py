"""Real AudioTransport using arecord/aplay subprocesses -- same
subprocess pattern pixel-ai/pixel_tts.py already proved working on
this exact hardware (stdin=DEVNULL, start_new_session=True so playback
can't grab the controlling terminal).

capture_chunks() is NOT implemented as true continuous streaming here.
That's real Milestone 2 scope once wake-word/VAD exists -- this device
has neither yet (openWakeWord needs an ARMv6 wheel that doesn't exist;
see docs/decisions/0016). This transport is built for the push-to-talk
demo in voice_loop_demo.py, which records a bounded clip between two
keypresses via its own helper, not through this interface's streaming
method. play()/stop_playback()/is_muted() map directly to the real
interface and are implemented for real.
"""
import asyncio
import os
import subprocess
import tempfile
from collections.abc import AsyncIterator

from .interfaces import AudioTransport


def _popen_kwargs() -> dict:
    return dict(stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


class RealAudioTransport(AudioTransport):
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None

    async def capture_chunks(self) -> AsyncIterator[bytes]:
        raise NotImplementedError(
            "Continuous streaming capture isn't built for this push-to-talk "
            "demo -- see voice_loop_demo.py's record_clip() for the bounded-"
            "clip recording this transport is actually paired with."
        )
        yield b""  # pragma: no cover -- unreachable, keeps this an async generator

    async def play(self, audio: bytes) -> None:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(audio)
            self._proc = subprocess.Popen(["aplay", "-q", path], **_popen_kwargs())
            await asyncio.get_event_loop().run_in_executor(None, self._proc.wait)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
            self._proc = None

    async def stop_playback(self) -> None:
        if self._proc is None or self._proc.poll() is not None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self._proc.kill()

    def is_muted(self) -> bool:
        return False  # no physical mute switch on this device yet
