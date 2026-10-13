"""OpenAI Whisper SpeechRecognitionBackend implementation. Same
lightweight requests-based HTTP pattern as openai_backend.py/
claude_backend.py -- not the official SDK.
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

    async def transcribe(self, audio: bytes) -> str:
        api_key = require_env("OPENAI_API_KEY")

        def _do_request():
            return requests.post(
                _API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("audio.wav", audio, "audio/wav")},
                data={"model": self._model},
                timeout=30,
            )

        response = await asyncio.to_thread(_do_request)
        response.raise_for_status()
        return response.json()["text"]
