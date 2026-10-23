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
from companion_robot.reading.word_timing import WordTiming, parse_word_timings, pcm_to_wav_bytes

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

    async def transcribe_with_word_timestamps(self, pcm_audio: bytes) -> list[WordTiming]:
        """Decision 0098: NOT for the child's mic input (see
        transcribe() above) -- transcribes Chitti's OWN synthesized
        speech to recover real, audio-grounded word timestamps for
        the teleprompter-style highlight, instead of guessing from a
        simulated reading pace (decision 0088's own reason the old
        WPM-based teleprompter desynced on real hardware).
        `pcm_audio` is raw PCM -- OpenAITTSBackend's own output
        format -- wrapped in a real WAV container here since the
        endpoint needs an actual audio file, not bare samples. Not
        part of the SpeechRecognitionBackend ABC -- an additive
        capability a caller checks for with getattr/hasattr, same as
        every other "degrade gracefully if absent" feature in this
        codebase, so no other backend or test fake needs to implement
        it."""
        api_key = require_env("OPENAI_API_KEY")
        wav_bytes = pcm_to_wav_bytes(pcm_audio)
        data = {
            "model": self._model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "word",
        }

        def _do_request():
            return self._session.post(
                _API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data=data,
                timeout=30,
            )

        response = await asyncio.to_thread(_do_request)
        response.raise_for_status()
        return parse_word_timings(response.json())
