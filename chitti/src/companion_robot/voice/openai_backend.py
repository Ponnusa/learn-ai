"""OpenAI LanguageModelBackend implementation (decision 0004's modular
pipeline). Same lightweight requests-based pattern as
pixel-ai/pixel_direct_llm.py, not the official SDK -- keeps the
dependency footprint small, and this exact HTTP shape is already
proven working there.
"""
import asyncio

import requests

from companion_robot.config.loader import require_env

from .interfaces import LanguageModelBackend

_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAILanguageModelBackend(LanguageModelBackend):
    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model

    async def generate_reply(
        self, messages: list[dict], system_prompt: str
    ) -> tuple[str, str]:
        api_key = require_env("OPENAI_API_KEY")
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
        }
        # requests is blocking -- offloaded so this coroutine doesn't
        # stall the event loop, same reasoning as pixel-ai's own
        # executor-offloading in pixel_openai_voice_semantic.py.
        response = await asyncio.to_thread(
            requests.post,
            _API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        return reply, self._model
