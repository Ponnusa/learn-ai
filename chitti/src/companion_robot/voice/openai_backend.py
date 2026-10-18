"""OpenAI LanguageModelBackend implementation (decision 0004's modular
pipeline). Same lightweight requests-based pattern as
pixel-ai/pixel_direct_llm.py, not the official SDK -- keeps the
dependency footprint small, and this exact HTTP shape is already
proven working there.

Decision 0047: `max_tokens` wasn't sent at all here before -- the
Claude backend's own `__init__` already had one (`max_tokens: int =
1024`), but this one didn't, so every call (including
ConversationService.classify_intent()'s one-word classification) was
left uncapped. Real Pi timing logs showed classify_intent() alone
taking 5.19s for what should be a single word, and reply_generation
consistently running 3-10x this project's own earlier benchmark
(decision 0012) -- an unbounded response length is a real, structural
contributor to both, not just occasional bad luck. `_DEFAULT_MAX_TOKENS`
is a generous cap for this project's own "short, warm reply" prompt
style (every real reply observed so far is well under half of it), so
it shouldn't truncate anything that was actually working; callers that
need a much tighter cap (classify_intent()'s one-word answer) pass
their own.
"""
import asyncio

import requests

from companion_robot.config.loader import require_env

from .interfaces import LanguageModelBackend

_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_MAX_TOKENS = 300


class OpenAILanguageModelBackend(LanguageModelBackend):
    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        max_tokens: int | None = _DEFAULT_MAX_TOKENS,
        temperature: float | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def generate_reply(
        self, messages: list[dict], system_prompt: str
    ) -> tuple[str, str]:
        api_key = require_env("OPENAI_API_KEY")
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
        }
        if self._max_tokens is not None:
            payload["max_tokens"] = self._max_tokens
        if self._temperature is not None:
            payload["temperature"] = self._temperature
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
