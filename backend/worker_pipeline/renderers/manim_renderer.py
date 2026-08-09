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
     worker's render_video() Docker invocation elsewhere in worker.py.

PORT NOTE: dev repo resolved _PROMPTS_DIR three levels up from
backend/pipeline/renderers/ to backend/prompts/. This module now lives at
worker_pipeline/renderers/, with the copied prompt files at
worker_pipeline/prompts/ — two levels up, not three.

CACHING: mirrors video_renderer.py's pattern — one hash covering
generation_prompt + narration_text + subject_area (narration is baked
directly into the generated code's voiceover block, so a narration-only
change still needs a fresh render, same as a prompt change), checked BEFORE
paying for a Claude call + a full Docker render. Previously this renderer
never checked the cache at all — every rerun regenerated from scratch even
when nothing had changed.

NO TEMPERATURE OVERRIDE: newer Claude models (claude-sonnet-5 and later)
reject an explicit `temperature` kwarg outright (`400 - temperature is
deprecated for this model`) — the API default is used instead, matching how
this call site should behave regardless of which Claude model is configured.
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
from ..asset_manifest import AssetRef, check_cache, compute_prompt_hash, register_asset
from ..schema import Segment
from ..tts import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, AZURE_VOICE_NAME
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

VOICE (critical — other segments in this same lesson use a fixed narrator voice):
Call self.set_speech_service(AzureService(voice="{AZURE_VOICE_NAME}")) — use EXACTLY this
voice name, character for character. Do NOT choose a different voice. Every segment in this
lesson (Manim, image, video) must sound like the same narrator; picking a different voice
here breaks that consistency.

TIMING SAFETY (critical — this has caused render failures before):
Any time you compute a self.wait(...) duration or an animation's run_time by subtracting
elapsed time from a target duration (e.g. tracker.duration - X, or remaining_time - Y),
the result can come out zero or negative if your animations already used up the budget.
Manim crashes on a non-positive wait/run_time. ALWAYS clamp with max(): use
self.wait(max(0.3, computed_value)) and run_time=max(0.3, computed_value), never the raw
subtraction. Apply this to EVERY computed wait/run_time in the scene, not just one.

Output ONLY the Python code for the scene (imports + one Scene subclass), no explanation,
no markdown fences."""

    raw = call_with_retry(
        model=MODEL,
        max_tokens=16000,
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
    if not AZURE_SPEECH_KEY:
        raise RuntimeError(
            "AZURE_SPEECH_KEY not set — manim_voiceover's AzureService would otherwise "
            "try to interactively prompt for it inside the container and crash with "
            "EOFError (no stdin attached to a non-interactive docker run)."
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
        "-e", f"AZURE_SUBSCRIPTION_KEY={AZURE_SPEECH_KEY}",
        "-e", f"AZURE_SERVICE_REGION={AZURE_SPEECH_REGION}",
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
            # One hash covering prompt + narration + subject — narration is
            # baked directly into the generated code's voiceover block, so a
            # narration-only change still needs a fresh render (same
            # reasoning as video_renderer.py's clip_hash).
            clip_hash = compute_prompt_hash(
                f"{segment.generation_prompt}||{segment.narration_text}", "", segment.subject_area,
            )
            segment.prompt_hash = clip_hash

            cached = check_cache(clip_hash, "manim_clip", segment.id, ".mp4")
            if cached:
                logger.info(f"[manim_renderer] cache hit for segment {segment.id} — skipping Claude+Docker")
                segment.clip_url = cached.url
                segment.actual_duration_seconds = segment.target_duration_seconds
                segment.status = "rendered"
                segment.error_message = None
                return cached

            code = generate_manim_code(segment)
            segment.generated_code = code

            seg_work_dir = os.path.join(self._work_dir, f"manim_{segment.id}")
            clip_path = render_code_to_clip(code, segment.id, seg_work_dir)

            clip_ref = register_asset(clip_path, segment.id, "manim_clip", clip_hash)

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
