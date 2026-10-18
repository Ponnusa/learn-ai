"""OpenAI Whisper SpeechRecognitionBackend implementation. Same
lightweight requests-based HTTP pattern as openai_backend.py/
claude_backend.py -- not the official SDK.

Decision 0049: holds one persistent `requests.Session`, reused for
every call, instead of the bare `requests.post(...)` function (which
opens a brand-new connection, full TCP/TLS handshake included, on
every single call). See voice/openai_backend.py's module docstring for
the real-hardware evidence this was based on.
"""
import asyncio

import requests

from companion_robot.config.loader import require_env

from .interfaces import SpeechRecognitionBackend

_API_URL = "https://api.openai.com/v1/audio/transcriptions"
_DEFAULT_MODEL = "whisper-1"


class OpenAIWhisperBackend(SpeechRecognitionBackend):
    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model
        self._session = requests.Session()

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        api_key = require_env("OPENAI_API_KEY")
        data = {"model": self._model}
        if language is not None:
            data["language"] = language

        def _do_request():
            return self._session.post(
                _API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("audio.wav", audio, "audio/wav")},
                data=data,
                timeout=30,
            )

        response = await asyncio.to_thread(_do_request)
        response.raise_for_status()
        return response.json()["text"]
