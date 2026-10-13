"""Typed interfaces for the Voice Interaction Engine (spec section 4).

Milestone 0: signatures and docstrings only. Every method raises
NotImplementedError -- no concrete backend exists yet (see
docs/architecture.md's AI backend comparison table for why the choice
between SpeechToSpeechBackend and the modular ASR+LLM+TTS path is still
open).
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class VoiceEvent:
    """Placeholder base type for events a SpeechToSpeechBackend yields.

    Milestone 2 will define concrete event types (turn-state changes,
    transcript deltas, audio deltas, tool calls) once a backend is
    chosen -- mirroring the event types pixel-ai/pixel_openai_voice_semantic.py
    already handles for one specific provider.
    """


class SpeechToSpeechBackend(ABC):
    """A single full-duplex streaming voice backend (spec section 4).

    Mirrors the proven shape of pixel-ai/pixel_openai_voice_semantic.py's
    websocket receive loop (VAD-driven turn state, barge-in via immediate
    playback cancellation, tool-calling) behind a provider-neutral
    contract -- spec section 4 forbids requiring a specific cloud
    provider or model vendor.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establishes the streaming session.

        Must raise on failure rather than silently no-op -- callers rely
        on this to drive reconnect/offline-mode logic (spec section 9).
        """
        raise NotImplementedError

    @abstractmethod
    async def send_audio_chunk(self, chunk: bytes) -> None:
        """Streams one chunk of captured microphone audio to the backend."""
        raise NotImplementedError

    @abstractmethod
    def events(self) -> AsyncIterator[VoiceEvent]:
        """Yields VoiceEvents as they arrive (turn-state changes,
        transcript deltas, audio deltas, tool calls)."""
        raise NotImplementedError

    @abstractmethod
    async def interrupt(self) -> None:
        """Cancels the in-flight response -- barge-in.

        Spec section 4 target: interruption-to-playback-stop latency
        below 200ms under supported conditions. This method's own
        latency is part of that budget; it must not block on network
        I/O to take effect locally.
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Cleanly ends the streaming session."""
        raise NotImplementedError


class SpeechRecognitionBackend(ABC):
    """ASR step of the modular ASR+LLM+TTS alternative (spec section 4).

    Reference precedent: pixel-ai/local_stt_server.py (faster-whisper
    behind a one-endpoint HTTP server) -- a real, working local-ASR
    design, though built for a separate "fast machine," not proven on
    a Pi 5 alone.
    """

    @abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        """Returns the transcribed text for one complete utterance."""
        raise NotImplementedError


class LanguageModelBackend(ABC):
    """LLM step of the modular ASR+LLM+TTS alternative (spec section 4).

    Mirrors pixel-ai/pixel_direct_llm.py and pixel_direct_claude.py's
    proven `ask(messages, system_prompt) -> (reply, model)` contract --
    a same-shape, swappable provider pair already built and tested
    there.
    """

    @abstractmethod
    async def generate_reply(
        self, messages: list[dict], system_prompt: str
    ) -> tuple[str, str]:
        """Returns (reply_text, model_name_used).

        For conversational replies and explanations only -- this
        backend must never be trusted to judge correctness for the
        Education Engine's activities (spec section 7: the engine
        decides, the model only explains/hints).
        """
        raise NotImplementedError


class TextToSpeechBackend(ABC):
    """TTS step of the modular ASR+LLM+TTS alternative (spec section 4).

    See ../../docs/model_and_licence_inventory.md for why pixel-ai's
    gTTS is explicitly rejected as a candidate implementation here
    (undocumented, unofficial endpoint, no commercial terms).
    """

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Returns synthesized audio bytes (format defined by the
        concrete implementation)."""
        raise NotImplementedError
