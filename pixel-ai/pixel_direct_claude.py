"""Direct Claude (Anthropic) text completion -- a separate, parallel
option to pixel_direct_llm.py (OpenAI), not a replacement for it.

pixel_direct_llm.py deliberately chose OpenAI to mirror LearnX's own
real chat_response provider choice (checked in backend/services/
ai_router.py). That symmetry was a tie-breaker, not the actual goal --
reply quality for hard STEM questions is. Claude's Sonnet/Opus tier has
generally had a stronger reputation on STEM/math reasoning benchmarks
than plain gpt-4o (OpenAI's strongest STEM performance comes from its
dedicated reasoning models, not gpt-4o, and those are too slow for a
voice assistant waiting on a reply) -- worth it for this module's job
even though it means diverging from LearnX's own provider choice.

Same direct-`requests`, no-SDK pattern as pixel_direct_llm.py, and the
exact same ask(messages, system_prompt, tier=None) -> (reply, model)
interface, so a caller can switch between the two with a one-line
import change. Reuses pixel_direct_llm.classify_difficulty() rather
than duplicating the same heuristic a second time -- both modules are
answering the same "how hard is this question" question, just handing
it to a different provider afterward.

Model names: "Haiku 4.5"/"Sonnet 5.5" are the current Claude lineup
-- claude-haiku-4-5-20251001 and claude-sonnet-5-5. Note LearnX's own
backend (ai_router.py) is still pinned to older claude-sonnet-4-6/
claude-opus-4-7 for its video pipeline -- that's LearnX's repo to
update, not touched here.

IMPORTANT COST NOTE: same as pixel_direct_llm.py -- a Claude
subscription is a completely separate product from API billing. This
calls the Anthropic API directly, billed per token.
"""
import os

import requests
from dotenv import load_dotenv

from pixel_direct_llm import classify_difficulty  # noqa: F401 -- re-exported for callers

# Standalone module -- loads its own .env, same reasoning as
# pixel_direct_llm.py's identical comment (import order isn't
# reliable to depend on for this).
load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SIMPLE_MODEL = os.environ.get("PIXEL_CLAUDE_SIMPLE_MODEL", "claude-haiku-4-5-20251001")
COMPLEX_MODEL = os.environ.get("PIXEL_CLAUDE_COMPLEX_MODEL", "claude-sonnet-5-5")

_ANTHROPIC_VERSION = "2023-06-01"


def ask(
    messages: list[dict],
    system_prompt: str,
    tier: str | None = None,
) -> tuple[str, str]:
    """Same contract as pixel_direct_llm.ask(): messages is conversation
    history as [{"role": "user"|"assistant", "content": ...}], NOT
    including the system prompt -- Anthropic's Messages API takes that
    as its own top-level `system` field, not a system-role message in
    the list, unlike OpenAI's shape. tier picked from the latest user
    message via pixel_direct_llm.classify_difficulty() if not given
    explicitly. Returns (reply_text, model_used)."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set -- direct Claude tier unavailable.")

    if tier is None:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        tier = classify_difficulty(last_user)

    model = COMPLEX_MODEL if tier == "complex" else SIMPLE_MODEL

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": _ANTHROPIC_VERSION,
        },
        json={
            "model": model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": 400,
        },
        timeout=30,
    )
    resp.raise_for_status()
    reply = resp.json()["content"][0]["text"].strip()
    return reply, model
