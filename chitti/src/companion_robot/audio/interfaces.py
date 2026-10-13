"""Typed interface for the Audio Engine's hardware boundary (spec section
3.2.B, 4). Milestone 0: signature and docstrings only.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class AudioTransport(ABC):
    """Microphone capture / speaker playback, hardware-independent.

    Deliberately separate from SpeechToSpeechBackend/TextToSpeechBackend
    (companion_robot.voice) -- this interface owns only raw audio I/O,
    so it can be mocked for development before real Pi 5 + mic + speaker
    hardware exists, same spirit as pixel-ai/pixel_face.py's eventual
    SDL-driver-fallback handling, but designed in from day one here
    instead of discovered after the fact on real hardware.

    A hardware mute (spec section 4) must prevent capture at this layer
    regardless of software or cloud state -- is_muted() must reflect the
    physical switch's actual state, not a software flag that could be
    overridden remotely.
    """

    @abstractmethod
    def capture_chunks(self) -> AsyncIterator[bytes]:
        """Yields raw microphone audio chunks as they're captured.

        Must yield nothing (not raise) while is_muted() is True --
        muting is enforced here, not left to callers to check.
        """
        raise NotImplementedError

    @abstractmethod
    async def play(self, audio: bytes) -> None:
        """Plays back audio. Must be cancellable via stop_playback()
        from another task -- this is what makes barge-in possible."""
        raise NotImplementedError

    @abstractmethod
    async def stop_playback(self) -> None:
        """Immediately stops any in-progress playback (barge-in).

        Mirrors pixel-ai/pixel_tts.py's stop() -- terminate the
        playback process/stream directly rather than waiting for it to
        finish naturally.
        """
        raise NotImplementedError

    @abstractmethod
    def is_muted(self) -> bool:
        """Reflects the physical mute switch's actual current state."""
        raise NotImplementedError
