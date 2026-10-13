"""Software-only AudioTransport for development without real mic/
speaker/mute-switch hardware (no hardware in hand yet). capture_chunks()
yields nothing until a test/dev caller feeds it via feed_chunk() --
there's no real microphone to read from. play()/stop_playback() just
track state instead of touching real audio.
"""
import asyncio
import logging
from collections.abc import AsyncIterator

from .interfaces import AudioTransport

logger = logging.getLogger(__name__)


class MockAudioTransport(AudioTransport):
    def __init__(self) -> None:
        self._muted = False
        self._playing = False
        self._queue: "asyncio.Queue[bytes]" = asyncio.Queue()

    async def capture_chunks(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._queue.get()
            if self._muted:
                # Muting is enforced here, not left to callers to check
                # (same contract as the real AudioTransport interface).
                continue
            yield chunk

    async def feed_chunk(self, chunk: bytes) -> None:
        """Test/dev hook -- simulates a chunk arriving from a real mic.

        Drops immediately if currently muted, matching real hardware:
        a physically muted mic never digitizes/produces the audio in
        the first place, so there's nothing to buffer and later replay
        once unmuted. The check in capture_chunks() stays too, as
        defense-in-depth against a mute toggling mid-flight.
        """
        if self._muted:
            return
        await self._queue.put(chunk)

    async def play(self, audio: bytes) -> None:
        self._playing = True
        logger.info("MockAudioTransport playing %d bytes", len(audio))
        self._playing = False

    async def stop_playback(self) -> None:
        self._playing = False
        logger.info("MockAudioTransport playback stopped")

    def is_muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> None:
        """Test/dev hook -- simulates the physical mute switch toggling.
        A real implementation would read this from an actual GPIO pin,
        never from a settable software flag like this one."""
        self._muted = muted
        logger.info("MockAudioTransport mute -> %s", muted)

    @property
    def is_playing(self) -> bool:
        """Test/dev hook -- not part of the AudioTransport interface."""
        return self._playing
