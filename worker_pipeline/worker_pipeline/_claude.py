"""
Shared standalone Anthropic client + retry helper for pipeline modules.

Deliberately not imported from main.py — main.py has module-level FastAPI/DB/R2
setup that pipeline modules (storyboard.py, manim_renderer.py, ...) shouldn't
trigger just to make a Claude call. Extracted here once a third module needed
the exact same retry logic storyboard.py had inlined — re-point this at
main.py's shared claude_with_retry() at the Sprint 6 port, where the pipeline
lives alongside the rest of the app instead of needing to stay independently
importable.
"""
import logging
import os
import threading
import time
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

MODEL = os.getenv("CLAUDE_MODEL_NAME", "claude-sonnet-4-6")
_RETRY_DELAYS = [5, 15, 45, 135]

_client: Optional[anthropic.Anthropic] = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def call_with_retry(**kwargs) -> str:
    """Same overloaded/529 backoff schedule as main.py's claude_with_retry (5s/15s/45s/135s).
    Always uses streaming so large max_tokens values don't hit the SDK's 10-minute non-streaming limit."""
    client = get_client()
    tid = threading.get_ident()
    model = kwargs.get("model", MODEL)
    max_tokens = kwargs.get("max_tokens", "?")
    print(f"[claude] thread={tid} START  model={model} max_tokens={max_tokens}", flush=True)
    t0 = time.time()
    last_exc = None
    for attempt, delay in enumerate(_RETRY_DELAYS, 1):
        try:
            with client.messages.stream(**kwargs) as stream:
                text = stream.get_final_text()
            if text:
                elapsed = time.time() - t0
                print(f"[claude] thread={tid} DONE   elapsed={elapsed:.1f}s len={len(text)}", flush=True)
                return text.strip()
            raise RuntimeError("Claude response contained no text (only thinking/other blocks)")
        except Exception as exc:
            last_exc = exc
            err = str(exc)
            is_overloaded = "overloaded" in err.lower() or "529" in err
            if is_overloaded and attempt < len(_RETRY_DELAYS):
                print(f"[claude] thread={tid} OVERLOADED attempt={attempt} — retrying in {delay}s", flush=True)
                logger.warning(f"⚠️ Claude overloaded (attempt {attempt}) — retrying in {delay}s")
                time.sleep(delay)
            else:
                print(f"[claude] thread={tid} ERROR  elapsed={time.time()-t0:.1f}s: {err[:120]}", flush=True)
                raise
    raise last_exc  # pragma: no cover — unreachable, loop always returns or raises
