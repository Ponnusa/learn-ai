"""Real AudioTransport using arecord/aplay subprocesses -- same
subprocess pattern pixel-ai/pixel_tts.py already proved working on
this exact hardware (stdin=DEVNULL, start_new_session=True so playback
can't grab the controlling terminal).

CAPTURE_DEVICE/PLAYBACK_DEVICE: pixel-ai's own README documents real
hardware experience that ALSA's "default" device often does NOT route
to the actual USB mic/speaker on this hardware -- every one of its
voice scripts sets PIXEL_MIC_DEVICE/PIXEL_SPEAKER_DEVICE explicitly
(e.g. "plughw:1,0", found via `arecord -l`/`aplay -l`) rather than
relying on "default". Same real constraint applies here, so the same
override is exposed -- under chitti's own env var names, not pixel-ai's,
since the two projects' configs are otherwise fully independent (decision
0001), even though it's the same physical device and likely the same
value. voice_loop_demo.py's capture helper imports CAPTURE_DEVICE from
here rather than duplicating this env-var read.

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

CAPTURE_DEVICE = os.environ.get("CHITTI_MIC_DEVICE", "default")
PLAYBACK_DEVICE = os.environ.get("CHITTI_SPEAKER_DEVICE", "default")


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
            self._proc = subprocess.Popen(
                ["aplay", "-D", PLAYBACK_DEVICE, "-q", path], **_popen_kwargs()
            )
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
