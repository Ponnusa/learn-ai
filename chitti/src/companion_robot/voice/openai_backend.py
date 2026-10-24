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

Decision 0049: `requests.post(...)` (the bare module-level function)
creates a brand-new, throwaway Session internally on every single
call -- no TCP/TLS connection reuse across calls, even to the same
host seconds apart. Real Pi timing logs showed this plainly: capping
classify_intent() to max_tokens=10 (decision 0047) didn't move its
latency at all (5.19s -> 5.74s, unchanged) -- a payload-independent
floor is the signature of per-call connection setup, not response
size. Each backend instance now keeps one persistent `requests.Session`
and reuses it for every call, so the TCP/TLS handshake happens once
(or occasionally, as pooled connections expire) instead of every time.
A connection that goes idle and gets closed by the server is handled
transparently by urllib3's own connection pool -- nothing here needs
to detect or recreate that; only a connection that actually dies
mid-request raises, same as it already could before this change.
"""
import asyncio

import requests

from companion_robot.config.loader import openai_request

from .interfaces import LanguageModelBackend

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
        self._session = requests.Session()

    async def generate_reply(
        self, messages: list[dict], system_prompt: str
    ) -> tuple[str, str]:
        url, headers, model = openai_request("chat/completions", self._model)
        payload = {
            "model": model,
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
            self._session.post,
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        return reply, model
