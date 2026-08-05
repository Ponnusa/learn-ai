"""
Manim segment renderer.

Two genuinely different pieces live here:

  1. Codegen (generate_manim_code) — a real Claude API call, same shape and
     just as testable as storyboard.py and image_renderer.py's Nano Banana
     call. Reuses the EXISTING, proven style-guide prompts from
     backend/prompts/ (base_prompt.txt + subject-specific) rather than
     re-authoring animation-quality rules from scratch — the same source of
     truth main.py's build_system_prompt() draws from, just read directly off
     disk instead of importing main.py (same reasoning as storyboard.py: main
     has module-level FastAPI/DB/R2 setup pipeline modules shouldn't trigger).
     Scoped to ONE short segment, not a whole lesson — the lesson-level
     decomposition already happened in storyboard.py.

  2. Docker render (render_code_to_clip) — turns generated code into an
     actual mp4 via `docker run manim-with-voiceover`, matching this same
     worker's render_video() Docker invocation elsewhere in worker.py — this
     is the piece that only ever worked on the GCP VM, and now runs for real
     here as of the Sprint 6 port (dev-repo version could only reach the
     honest "Docker not available" error, since it had no Docker/manim at
     all).

PORT NOTE: dev repo resolved _PROMPTS_DIR three levels up from
backend/pipeline/renderers/ to backend/prompts/. This module now lives at
worker_pipeline/renderers/, with the copied prompt files at
worker_pipeline/prompts/ — two levels up, not three.
"""
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional
from pathlib import Path

from .._claude import MODEL, call_with_retry
from ..asset_manifest import AssetRef, compute_prompt_hash, register_asset
from ..schema import Segment
from .base import Renderer

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_SUBJECT_PROMPT_FILES = {
    "physics": "physics_prompt.txt",
    "chemistry": "chemistry_prompt.txt",
    "mathematics": "mathematics_prompt.txt",
    "economics": "economics_prompt.txt",
}


def _load_prompt_section(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(f"⚠️ Prompt section not found: {filename}")
        return ""


def build_system_prompt(subject_area: str, aspect_ratio: str) -> str:
    prompt = _load_prompt_section("base_prompt.txt")
    subject_file = _SUBJECT_PROMPT_FILES.get(subject_area)
    if subject_file:
        prompt += "\n\n" + _load_prompt_section(subject_file)
    prompt += f"\n\nTARGET_ASPECT_RATIO: {aspect_ratio}\n"
    return prompt


def generate_manim_code(segment: Segment) -> str:
    """
    Single Claude call producing ONE short Manim scene implementing just this
    segment's storyboard direction — not the whole lesson. Raises on
    truncated/invalid code (checked via compile()) rather than returning it.
    """
    system_prompt = build_system_prompt(segment.subject_area, segment.aspect_ratio)

    user_prompt = f"""Implement ONE short Manim scene for a single segment of a longer lesson video.
This segment is {segment.target_duration_seconds:.0f} seconds long and covers ONLY the direction
below — do not attempt to cover the whole lesson topic, and do not re-derive or change any values.

ANIMATION DIRECTION (from the storyboard — implement exactly this):
{segment.generation_prompt}

VOICEOVER TEXT (verbatim, wrap in exactly one `with self.voiceover(text=...)` block):
{segment.narration_text}

SUBJECT: {segment.subject_area}
TARGET DURATION: {segment.target_duration_seconds:.0f} seconds

Output ONLY the Python code for the scene (imports + one Scene subclass), no explanation,
no markdown fences."""

    raw = call_with_retry(
        model=MODEL,
        max_tokens=4000,
        temperature=0.2,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    code = raw.strip()
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    elif code.startswith("```"):
        code = code[3:].strip()
    if code.endswith("```"):
        code = code[:-3].strip()

    try:
        compile(code, "<generated-segment>", "exec")
    except SyntaxError as exc:
        raise ValueError(f"Generated Manim code has a syntax error (likely truncated): {exc}")

    return code


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _extract_scene_name(code: str) -> str:
    match = re.search(r"class\s+(\w+)\s*\(.*Scene.*\)\s*:", code)
    if not match:
        raise ValueError("Could not find a Scene subclass in generated code")
    return match.group(1)


def render_code_to_clip(code: str, segment_id: str, work_dir: str) -> str:
    """
    Render generated Manim code to an mp4 via Docker, mirroring
    learnai/worker.py's render_video() Docker invocation. Raises immediately,
    honestly, if Docker isn't available — see module docstring.
    """
    if not _docker_available():
        raise RuntimeError(
            "Manim rendering requires Docker + the manim-with-voiceover image — "
            "only available on the GCP worker (learnai/worker.py). This dev repo "
            "can generate code (see generate_manim_code) but cannot render it "
            "locally; full render validation happens at the Sprint 6 port."
        )

    scene_name = _extract_scene_name(code)
    os.makedirs(work_dir, exist_ok=True)
    code_file = os.path.join(work_dir, f"{segment_id}.py")
    with open(code_file, "w", encoding="utf-8") as f:
        f.write(code)

    media_dir = os.path.join(work_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    cmd = [
        "docker", "run", "--rm", "--init", "--user", "root",
        "-v", f"{os.path.abspath(work_dir)}:/manim",
        "-v", f"{os.path.abspath(media_dir)}:/output",
        "-e", "PYTHONPATH=/manim",
        "--workdir", "/manim",
        "manim-with-voiceover:latest",
        "manim", "-qm", "--media_dir", "/output", "--progress_bar", "none", "--disable_caching",
        f"{segment_id}.py", scene_name,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Manim Docker render failed:\n{result.stderr[-1000:]}")

    for root, _dirs, files in os.walk(media_dir):
        for fname in files:
            if fname == f"{scene_name}.mp4":
                return os.path.join(root, fname)
    raise RuntimeError("Manim render completed but output mp4 was not found")


class ManimRenderer(Renderer):
    def __init__(self, work_dir: Optional[str] = None):
        self._work_dir = work_dir or tempfile.gettempdir()

    def render(self, segment: Segment) -> AssetRef:
        segment.status = "generating"
        try:
            code = generate_manim_code(segment)
            segment.generated_code = code

            seg_work_dir = os.path.join(self._work_dir, f"manim_{segment.id}")
            clip_path = render_code_to_clip(code, segment.id, seg_work_dir)

            prompt_hash = compute_prompt_hash(segment.generation_prompt, "", segment.subject_area)
            segment.prompt_hash = prompt_hash
            clip_ref = register_asset(clip_path, segment.id, "manim_clip", prompt_hash)

            segment.clip_url = clip_ref.url
            segment.actual_duration_seconds = segment.target_duration_seconds
            segment.status = "rendered"
            segment.error_message = None
            return clip_ref

        except Exception as exc:
            segment.status = "failed"
            segment.retry_count += 1
            segment.error_message = str(exc)[:500]
            logger.error(f"[manim_renderer] segment {segment.id} failed: {exc}")
            raise
