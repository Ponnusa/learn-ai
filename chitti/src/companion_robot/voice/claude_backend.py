"""Claude LanguageModelBackend implementation (decision 0004's modular
pipeline). Same lightweight requests-based pattern as
pixel-ai/pixel_direct_claude.py -- Anthropic's Messages API shape
(system as a top-level field, not in the messages list; x-api-key
header, not Authorization: Bearer).

Decision 0049: holds one persistent `requests.Session`, reused for
every call, instead of the bare `requests.post(...)` function (which
opens a brand-new connection, full TCP/TLS handshake included, on
every single call). See voice/openai_backend.py's module docstring for
the real-hardware evidence this was based on.
"""
import asyncio

import requests

from companion_robot.config.loader import require_env

from .interfaces import LanguageModelBackend

_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class ClaudeLanguageModelBackend(LanguageModelBackend):
    def __init__(self, model: str = _DEFAULT_MODEL, max_tokens: int = 1024) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._session = requests.Session()

    async def generate_reply(
        self, messages: list[dict], system_prompt: str
    ) -> tuple[str, str]:
        api_key = require_env("ANTHROPIC_API_KEY")
        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        response = await asyncio.to_thread(
            self._session.post,
            _API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        reply = data["content"][0]["text"]
        return reply, self._model
