"""OpenAI TextToSpeechBackend implementation. Requests response_format
"wav" directly, so playback (audio/real.py's RealAudioTransport) can
use aplay without needing an mp3 decoder like pixel-ai's mpg123.
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

    async def synthesize(self, text: str) -> bytes:
        api_key = require_env("OPENAI_API_KEY")
        payload = {
            "model": self._model,
            "voice": self._voice,
            "input": text,
            "response_format": "wav",
        }
        response = await asyncio.to_thread(
            requests.post,
            _API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.content
