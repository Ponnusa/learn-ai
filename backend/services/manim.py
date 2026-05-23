"""
Manim video generation pipeline.
COPIED VERBATIM from AnimLearn main.py — DO NOT MODIFY PROMPTS.
Any prompt improvements must be made in AnimLearn first, then synced here.

Includes:
  - generate_manim_code_enhanced()  (full multi-layer pipeline)
  - fix_manim_colors()
  - ensure_numpy_import()
  - _trigger_video_generation()
"""
import re
import json
import httpx
from config import settings
from services.ai_router import claude_client, openai_client, get_model

# ── Paste AnimLearn prompts verbatim below ────────────────────────────────────
# TODO: Copy MANIM_SYSTEM_PROMPT, SVG_PROMPT, TRANSCRIPT_PROMPT,
#       CRITIC_PROMPT from AnimLearn main.py into this file.
#       They are intentionally left as stubs here — copy from source.

MANIM_SYSTEM_PROMPT = """
# PASTE FROM ANIMLEARN main.py
"""

SVG_SYSTEM_PROMPT = """
# PASTE FROM ANIMLEARN main.py
"""

TRANSCRIPT_SYSTEM_PROMPT = """
# PASTE FROM ANIMLEARN main.py
"""

CRITIC_SYSTEM_PROMPT = """
# PASTE FROM ANIMLEARN main.py
"""

# ─────────────────────────────────────────────────────────────────────────────


def fix_manim_colors(code: str) -> str:
    """Fix common Manim color issues — copied from AnimLearn."""
    # TODO: paste from AnimLearn main.py
    return code


def ensure_numpy_import(code: str) -> str:
    """Ensure numpy is imported — copied from AnimLearn."""
    if "import numpy" not in code:
        code = "import numpy as np\n" + code
    return code


async def generate_manim_code_enhanced(
    prompt: str,
    language: str = "en",
    max_duration: int = 60,
    aspect_ratio: str = "16:9",
) -> dict:
    """
    Full multi-layer AnimLearn pipeline:
      1. Generate teaching transcript  (Claude Sonnet)
      2. Generate SVG diagrams         (Claude Sonnet)
      3. Generate Manim code           (Claude Opus)
      4. Critic loop — validate & fix  (Claude Opus)
      5. Return {code, scene_name, svg_urls, transcript_markdown, verified_solution}

    TODO: Paste the full implementation from AnimLearn main.py.
    The function signature and return shape must remain identical.
    """
    # TODO: paste full implementation from AnimLearn main.py
    raise NotImplementedError(
        "Paste generate_manim_code_enhanced from AnimLearn main.py"
    )


def _trigger_video_generation(video_id: int, svg_urls: dict | None = None):
    """
    Trigger Cloud Run renderer — same payload as AnimLearn.
    Cloud Run reads generated_code + scene_name from the videos table.
    """
    if not settings.CLOUD_RUN_VIDEO_URL:
        return
    try:
        import threading
        def _call():
            httpx.post(
                settings.CLOUD_RUN_VIDEO_URL,
                json={"job_id": video_id, "svg_urls": svg_urls or {}},
                headers={"X-Secret": settings.CLOUD_RUN_SECRET},
                timeout=10,
            )
        threading.Thread(target=_call, daemon=True).start()
    except Exception:
        pass
