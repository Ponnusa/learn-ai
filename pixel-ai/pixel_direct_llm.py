"""Direct OpenAI text completion -- Pixel's one-hop replacement for ever
routing regular Q&A through LearnX's backend.

Supersedes the earlier pixel_ollama_cloud.py (same direct-`requests`-to-
OpenAI pattern, no SDK, same non-interfering standalone-file approach) --
folded in here rather than kept as a separate module, now with two model
tiers instead of one fixed cheap model.

Model choice mirrors LearnX's own real provider/model split, checked
directly in backend/services/ai_router.py's MODELS dict rather than
guessed: LearnX uses Claude only for its video pipeline (Manim code
generation, transcripts, SVGs) and OpenAI for chat (`chat_response` ->
gpt-4o). Since Pixel never generates video itself (that stays on LearnX's
backend, see pixel_brain.py's request_video()/poll_video()), there's no
reason for Pixel to touch Claude at all -- this follows LearnX's own
chat-path choice instead of picking a different provider for no reason:
  - simple  -> gpt-4o-mini (LearnX's own cheap-task model elsewhere in
               ai_router.py -- subject_detection, title_generation, etc.)
  - complex -> gpt-4o (exactly LearnX's own chat_response model)

IMPORTANT COST NOTE: an OpenAI subscription (ChatGPT Plus) is a
completely separate product from API billing -- this calls the API,
billed per token regardless of any consumer subscription. These two
model names are LearnX's own confirmed-live choices, not guessed, but
still worth one live `GET /v1/models` check against Pixel's own
OPENAI_API_KEY before relying on them -- access/availability can differ
per key even for the same model name.
"""
import os
import re

import requests

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
SIMPLE_MODEL = os.environ.get("PIXEL_DIRECT_SIMPLE_MODEL", "gpt-4o-mini")
COMPLEX_MODEL = os.environ.get("PIXEL_DIRECT_COMPLEX_MODEL", "gpt-4o")

# Same zero-latency keyword/length heuristic philosophy as
# pixel_ollama_router.classify() -- a pre-call routing decision (which
# model answers), not a second LLM call just to decide which LLM to call.
_COMPLEX_PATTERN = re.compile(
    r"\b(explain in detail|write (?:a|an|me)|essay|analyz[es]|analyse|"
    r"compare and contrast|history of|summari[sz]e|code for|program that|"
    r"solve|equation|derivative|integral|why does|how does)\b",
    re.IGNORECASE,
)
_COMPLEX_WORD_COUNT = 25


def classify_difficulty(text: str) -> str:
    """Returns "simple" or "complex" -- which model tier should answer
    `text`. Conservative on purpose: a false negative just means the
    cheaper model answers something it could've handled better; a false
    positive spends money unnecessarily on the pricier model."""
    if _COMPLEX_PATTERN.search(text) or len(text.split()) > _COMPLEX_WORD_COUNT:
        return "complex"
    return "simple"


def ask(
    messages: list[dict],
    system_prompt: str,
    tier: str | None = None,
) -> tuple[str, str]:
    """messages: conversation history as [{"role": "user"|"assistant",
    "content": ...}], NOT including the system prompt (passed
    separately so callers don't need to manage where it sits in the
    list). tier picked from the latest user message if not given
    explicitly. Returns (reply_text, model_used) -- the model name is
    returned so callers can log which tier actually answered, same
    spirit as pixel_ollama_router.log_routing() elsewhere in this
    project."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set -- direct LLM tier unavailable.")

    if tier is None:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        tier = classify_difficulty(last_user)

    model = COMPLEX_MODEL if tier == "complex" else SIMPLE_MODEL

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "max_tokens": 400,
        },
        timeout=30,
    )
    resp.raise_for_status()
    reply = resp.json()["choices"][0]["message"]["content"].strip()
    return reply, model
