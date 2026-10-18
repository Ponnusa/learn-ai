"""OpenAI TextToSpeechBackend implementation. Requests response_format
"pcm" -- raw 16-bit signed LE mono samples at 24kHz, no header -- so
playback (audio/real.py's RealAudioTransport) can stream it directly
into a persistent `aplay -t raw` process's stdin. Decision 0016's
addendum: a first version requested "wav" and reopened a fresh aplay
process per reply, which worked for the test client but on real
hardware silently lost the start of short replies to USB-device
warmup; raw PCM into one persistent process is what fixed it.
PLAYBACK_SAMPLE_RATE in audio/real.py must match the 24kHz this
returns.

Decision 0049: holds one persistent `requests.Session`, reused for
every call, instead of the bare `requests.post(...)` function (which
opens a brand-new connection, full TCP/TLS handshake included, on
every single call). See voice/openai_backend.py's module docstring for
the real-hardware evidence this was based on.
"""
import asyncio

import requests

from companion_robot.config.loader import require_env

from .interfaces import TextToSpeechBackend

_API_URL = "https://api.openai.com/v1/audio/speech"
_DEFAULT_MODEL = "tts-1"
_DEFAULT_VOICE = "alloy"


class OpenAITTSBackend(TextToSpeechBackend):
    def __init__(self, model: str = _DEFAULT_MODEL, voice: str = _DEFAULT_VOICE) -> None:
        self._model = model
        self._voice = voice
        self._session = requests.Session()

    async def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        api_key = require_env("OPENAI_API_KEY")
        # OpenAI's API accepts 0.25-4.0; out-of-range values are left
        # to surface as a clear API error rather than silently clamped
        # -- the Parent Controls UI constrains the input range instead.
        payload = {
            "model": self._model,
            "voice": self._voice,
            "input": text,
            "response_format": "pcm",
            "speed": speed,
        }
        response = await asyncio.to_thread(
            self._session.post,
            _API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.content
