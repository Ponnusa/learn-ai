"""
Manim segment renderer.

Two genuinely different pieces live here:

  1. Codegen — two paths:
     a. generate_manim_code(segment)  — single-segment path: one Claude call,
        one Scene class. Used when only one Manim segment needs generation, or
        as the retry/degrade fallback when unified codegen fails.
     b. generate_all_manim_code(segments)  — unified path: ONE Claude call for
        ALL non-cached Manim segments in the lesson, producing a single Python
        file with shared module-level constants (zone coords, colors, font
        sizes) and one Scene class per segment. The orchestrator calls this
        before the main render loop and pre-populates segment.generated_code +
        segment.generated_class_name so ManimRenderer.render() skips the
        per-segment Claude call entirely.
        Benefits: style consistency across segments (shared constants), N→1
        Claude API calls for a typical 3-segment lesson.

  2. Docker render (render_code_to_clip) — turns generated code into an
     actual mp4 via `docker run manim-with-voiceover`. Accepts an optional
     scene_name parameter so the unified path can specify which of the N
     classes in the shared file to render without re-parsing.

CACHING: per-segment, keyed on generation_prompt + narration_text + subject_area
(same as before unified codegen). Cache hits bypass BOTH the Claude call and
the Docker render. The orchestrator skips unified codegen if all Manim
segments are individually cached; ManimRenderer.render() still checks the
cache on entry so a segment that hits the cache is never re-rendered even
if the unified call already ran.

NO TEMPERATURE OVERRIDE: newer Claude models (claude-sonnet-5 and later)
reject an explicit `temperature` kwarg outright — the API default is used
instead.
"""
import logging
import os
import re
import shutil
import subprocess
import tempfile
from typing import List, Optional
from pathlib import Path

from .._claude import MODEL, call_with_retry
from ..asset_manifest import AssetRef, check_cache, compute_prompt_hash, log_manim_failure, register_asset
from ..schema import Segment
from ..tts import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, AZURE_VOICE_NAME, voice_for_language
from .base import Renderer

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# ── Bohr atom helper — injected into chemistry code before Docker render ──────

_ATOM_BOHR_CODE: str = '''
ATOM_CONFIGS = {
    "H":  ([1],             "#DDDDDD"),
    "He": ([2],             "#C8E8FF"),
    "Li": ([2, 1],          "#CC3333"),
    "Be": ([2, 2],          "#228844"),
    "B":  ([2, 3],          "#DD7700"),
    "C":  ([2, 4],          "#888888"),
    "N":  ([2, 5],          "#4477EE"),
    "O":  ([2, 6],          "#EE3333"),
    "F":  ([2, 7],          "#33BB77"),
    "Ne": ([2, 8],          "#99CCFF"),
    "Na": ([2, 8, 1],       "#FFCC22"),
    "Mg": ([2, 8, 2],       "#22AA55"),
    "Al": ([2, 8, 3],       "#AAAAAA"),
    "Si": ([2, 8, 4],       "#BBBBBB"),
    "P":  ([2, 8, 5],       "#FF7722"),
    "S":  ([2, 8, 6],       "#FFDD00"),
    "Cl": ([2, 8, 7],       "#44CC44"),
    "Ar": ([2, 8, 8],       "#AABBFF"),
    "K":  ([2, 8, 8, 1],    "#BB44AA"),
    "Ca": ([2, 8, 8, 2],    "#22AA44"),
}


def draw_bohr_atom(symbol, position=ORIGIN, scale=1.0, electron_color=YELLOW, shell_color=GRAY, shells=None, color=None):
    import math as _m
    if color is not None:
        electron_color = color
    cfg_shells, nuc_hex = ATOM_CONFIGS.get(symbol, ([1], "#888888"))
    if shells is None:
        shells = cfg_shells
    group = VGroup()
    nuc_r = 0.28 * scale
    nucleus  = Circle(radius=nuc_r, fill_color=ManimColor(nuc_hex), fill_opacity=1,
                      stroke_color=WHITE, stroke_width=1.5)
    sym_text = Text(symbol, font_size=int(16 * scale), color=WHITE)
    nuc_group = VGroup(nucleus, sym_text)
    nuc_group.move_to(position)
    group.add(nuc_group)
    base_radii = [0.62, 1.08, 1.54, 2.00]
    for i, count in enumerate(shells):
        r = base_radii[i] * scale
        ring = Circle(radius=r, stroke_color=shell_color, stroke_width=1.2,
                      fill_opacity=0, stroke_opacity=0.55).move_to(position)
        group.add(ring)
        for j in range(count):
            angle = (2 * _m.pi * j / count) - _m.pi / 2
            ex = position[0] + r * _m.cos(angle)
            ey = position[1] + r * _m.sin(angle)
            group.add(Dot(radius=0.072 * scale, color=electron_color).move_to([ex, ey, 0]))
    return group
'''


def _strip_llm_atom_definitions(code: str) -> str:
    import ast as _ast
    try:
        tree = _ast.parse(code)
    except SyntaxError:
        return code
    lines = code.splitlines(keepends=True)
    to_remove: set = set()
    for node in tree.body:
        if isinstance(node, _ast.FunctionDef) and node.name == 'draw_bohr_atom':
            for ln in range(node.lineno, node.end_lineno + 1):
                to_remove.add(ln)
        elif isinstance(node, _ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, _ast.Name) and tgt.id == 'ATOM_CONFIGS':
                    for ln in range(node.lineno, node.end_lineno + 1):
                        to_remove.add(ln)
    if not to_remove:
        return code
    result = ''.join(line for i, line in enumerate(lines, 1) if i not in to_remove)
    return re.sub(r'\n{3,}', '\n\n', result)


def inject_atom_helper(code: str, subject_area: str) -> str:
    if subject_area != "chemistry":
        return code
    if "draw_bohr_atom" not in code:
        return code
    code = _strip_llm_atom_definitions(code)
    match = re.search(r'^class\s+\w+', code, re.MULTILINE)
    if not match:
        return code
    insert_pos = match.start()
    return code[:insert_pos] + _ATOM_BOHR_CODE.strip() + "\n\n\n" + code[insert_pos:]

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


# ── Cache helper ──────────────────────────────────────────────────────────────

def _check_manim_cache(segment: Segment) -> Optional[AssetRef]:
    """
    Compute and store the per-segment cache key, then return the cached
    AssetRef if one exists (None = cache miss). Setting segment.prompt_hash
    here means ManimRenderer.render() can call register_asset with the same
    key without recomputing it.
    """
    clip_hash = compute_prompt_hash(
        f"{segment.generation_prompt}||{segment.narration_text}", "", f"{segment.subject_area}||{segment.language}",
    )
    segment.prompt_hash = clip_hash
    return check_cache(clip_hash, "manim_clip", segment.id, ".mp4")


# ── Class name helpers ────────────────────────────────────────────────────────

def _unified_class_name(segment: Segment) -> str:
    """
    Deterministic class name for a segment in the unified codegen path.
    Derived purely from segment.order so neither the orchestrator nor the
    renderer needs to parse the generated code to know what to render.
    """
    return f"Seg{segment.order}_Lesson"


# ── Single-segment codegen ────────────────────────────────────────────────────

def generate_manim_code(segment: Segment) -> str:
    """
    Single Claude call producing ONE short Manim scene implementing just this
    segment's storyboard direction — not the whole lesson. Raises on
    truncated/invalid code (checked via compile()) rather than returning it.
    Used when only one Manim segment needs generation or as fallback when
    unified codegen fails.
    """
    system_prompt = build_system_prompt(segment.subject_area, segment.aspect_ratio)

    seg_voice = voice_for_language(segment.language)
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
Call self.set_speech_service(AzureService(voice="{seg_voice}")) — use EXACTLY this
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
        max_tokens=32000,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    code = _strip_fences(raw)

    try:
        compile(code, "<generated-segment>", "exec")
    except SyntaxError as exc:
        raise ValueError(f"Generated Manim code has a syntax error (likely truncated): {exc}")

    return code


# ── Unified multi-segment codegen ─────────────────────────────────────────────

def generate_all_manim_code(segments: List[Segment]) -> str:
    """
    One Claude call producing ONE Python file with N scene classes — one per
    segment — plus shared module-level constants so every class uses the same
    zone coordinates, colors, and font sizes.

    Class names are deterministic (_unified_class_name) so the orchestrator
    can pre-populate segment.generated_class_name without parsing the output.

    Raises ValueError if any expected class is absent or the code has a syntax
    error — callers should catch and fall back to per-segment generation.
    """
    subject_area = segments[0].subject_area
    aspect_ratio = segments[0].aspect_ratio
    unified_voice = voice_for_language(segments[0].language)
    system_prompt = build_system_prompt(subject_area, aspect_ratio)

    seg_blocks = []
    for seg in segments:
        class_name = _unified_class_name(seg)
        seg_blocks.append(
            f"=== SEGMENT {seg.order} | class name MUST be exactly `{class_name}` "
            f"| {seg.target_duration_seconds:.0f}s ===\n"
            f"DIRECTION: {seg.generation_prompt}\n"
            f"VOICEOVER (verbatim, one self.voiceover block): {seg.narration_text}"
        )

    segments_text = "\n\n".join(seg_blocks)
    n = len(segments)

    user_prompt = f"""Generate ONE Python file containing {n} short Manim scene classes for
consecutive segments of a single lesson video. The segments must look visually consistent —
a student watching them back-to-back should feel they belong to the same lesson.

STRUCTURE RULES:
1. Define shared visual constants at module level BEFORE any class definition:
   - Layout zones  (e.g. LEFT_PANEL = LEFT * 3.0, RIGHT_PANEL = RIGHT * 2.8)
   - Color palette (e.g. ACCENT = YELLOW, BODY_TEXT = LIGHT_GRAY)
   - Font sizes    (e.g. TITLE_SIZE = 26, BODY_SIZE = 20)
   Reference these constants in every class — never repeat the same magic
   number in two different classes.
2. Write exactly {n} classes, named EXACTLY as specified in each segment header
   below. Deviating from those names causes the render to crash.
3. Every class must call:
   self.set_speech_service(AzureService(voice="{unified_voice}"))
4. Every class must contain exactly one voiceover context manager:
   with self.voiceover(text="...") as tracker:
5. Clamp ALL computed durations:
   self.wait(max(0.3, value))   run_time=max(0.3, value)
   Never use a raw subtraction result as a wait or run_time.

SEGMENTS TO IMPLEMENT:

{segments_text}

SUBJECT: {subject_area}
ASPECT RATIO: {aspect_ratio}

Output ONLY the Python code (imports + module-level constants + {n} classes).
No explanation, no markdown fences."""

    messages = [{"role": "user", "content": user_prompt}]

    for fix_attempt in range(2):  # attempt 0 = first try, attempt 1 = syntax-fix retry
        raw = call_with_retry(
            model=MODEL,
            max_tokens=32000,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )

        code = _strip_fences(raw)

        missing = [
            _unified_class_name(s) for s in segments
            if f"class {_unified_class_name(s)}" not in code
        ]
        if missing:
            raise ValueError(
                f"Unified codegen response is missing expected classes: {missing}. "
                "Output was likely truncated — falling back to per-segment generation."
            )

        try:
            compile(code, "<generated-lesson>", "exec")
            break  # valid code — exit retry loop
        except SyntaxError as exc:
            if fix_attempt == 0:
                logger.warning(
                    f"[manim_renderer] unified code has syntax error ({exc}) — retrying with fix prompt"
                )
                messages = [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": (
                        f"Your code has a Python syntax error: {exc}\n"
                        "Return the COMPLETE corrected Python file. "
                        "No explanation, no markdown fences."
                    )},
                ]
            else:
                raise ValueError(f"Unified Manim code has a syntax error after fix attempt: {exc}")

    logger.info(
        f"[manim_renderer] unified code generated: {n} classes, {len(code)} chars"
    )
    return code


# ── Shared fence-stripping util ───────────────────────────────────────────────

def _strip_fences(raw: str) -> str:
    code = raw.strip()
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    elif code.startswith("```"):
        code = code[3:].strip()
    if code.endswith("```"):
        code = code[:-3].strip()
    return code


# ── Docker render ─────────────────────────────────────────────────────────────

def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _extract_scene_name(code: str) -> str:
    match = re.search(r"class\s+(\w+)\s*\(.*Scene.*\)\s*:", code)
    if not match:
        raise ValueError("Could not find a Scene subclass in generated code")
    return match.group(1)


def render_code_to_clip(
    code: str,
    segment_id: str,
    work_dir: str,
    scene_name: Optional[str] = None,
    subject_area: str = "",
) -> str:
    """
    Render generated Manim code to an mp4 via Docker.

    `scene_name` — when provided, renders that specific class from the file
    (used by the unified path where the file contains multiple classes).
    When None, falls back to extracting the first Scene subclass from `code`
    (single-segment path behaviour, unchanged).
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

    code = inject_atom_helper(code, subject_area)
    resolved_scene = scene_name or _extract_scene_name(code)
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
        f"{segment_id}.py", resolved_scene,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"Manim Docker render failed:\n{result.stderr[-1000:]}")

    for root, _dirs, files in os.walk(media_dir):
        for fname in files:
            if fname == f"{resolved_scene}.mp4":
                return os.path.join(root, fname)
    raise RuntimeError("Manim render completed but output mp4 was not found")


# ── Auto-fix: ask Claude to repair Python errors before retry ─────────────────

_PYTHON_ERROR_PATTERNS = (
    "NameError", "AttributeError", "TypeError", "SyntaxError",
    "ValueError", "IndexError", "KeyError", "UnboundLocalError",
)


def _is_python_error(stderr: str) -> bool:
    return any(p in stderr for p in _PYTHON_ERROR_PATTERNS)


def fix_code_with_claude(code: str, error: str) -> str:
    """
    Ask Claude to fix a Python/Manim error in generated code.
    Returns corrected code, or raises if the fix itself has a syntax error.
    """
    raw = call_with_retry(
        model=MODEL,
        max_tokens=32000,
        system=[{"type": "text", "text": (
            "You are a Manim Python code fixer. "
            "You will be given broken Manim code and an error traceback. "
            "Return ONLY the complete corrected Python file — no explanation, no markdown fences."
        )}],
        messages=[{"role": "user", "content": (
            f"Fix this Manim Python error and return the complete corrected file.\n\n"
            f"ERROR:\n{error[-2000:]}\n\n"
            f"CODE:\n{code}"
        )}],
    )
    fixed = _strip_fences(raw)
    try:
        compile(fixed, "<fix-check>", "exec")
    except SyntaxError as exc:
        raise ValueError(f"Claude's fix still has a syntax error: {exc}")
    return fixed


# ── Renderer class ────────────────────────────────────────────────────────────

class ManimRenderer(Renderer):
    def __init__(self, work_dir: Optional[str] = None):
        self._work_dir = work_dir or tempfile.gettempdir()

    def render(self, segment: Segment) -> AssetRef:
        segment.status = "generating"
        try:
            # Cache check — always runs regardless of whether code was
            # pre-generated by the orchestrator's unified pass.
            cached = _check_manim_cache(segment)
            if cached:
                logger.info(
                    f"[manim_renderer] cache hit for segment {segment.id} — skipping render"
                )
                segment.clip_url = cached.url
                segment.actual_duration_seconds = segment.target_duration_seconds
                segment.status = "rendered"
                segment.error_message = None
                return cached

            if segment.generated_code is not None:
                # Unified path — orchestrator pre-generated all Manim segments
                # in one Claude call. Use the pre-populated code and class name.
                code = segment.generated_code
                scene_name = segment.generated_class_name or _unified_class_name(segment)
                logger.info(
                    f"[manim_renderer] rendering pre-generated segment {segment.id} "
                    f"(class {scene_name})"
                )
            else:
                # Single-segment fallback — generate now (one Claude call).
                logger.info(
                    f"[manim_renderer] single-segment codegen for {segment.id}"
                )
                code = generate_manim_code(segment)
                segment.generated_code = code
                scene_name = None  # render_code_to_clip will extract it

            seg_work_dir = os.path.join(self._work_dir, f"manim_{segment.id}")
            try:
                clip_path = render_code_to_clip(
                    code, segment.id, seg_work_dir, scene_name=scene_name,
                    subject_area=segment.subject_area,
                )
            except RuntimeError as render_exc:
                err_str = str(render_exc)
                if _is_python_error(err_str):
                    logger.warning(
                        f"[manim_renderer] Python error in segment {segment.id} — "
                        "asking Claude to fix before retry"
                    )
                    try:
                        code = fix_code_with_claude(code, err_str)
                        segment.generated_code = code
                        scene_name = _extract_scene_name(code)
                        clip_path = render_code_to_clip(
                            code, segment.id, seg_work_dir, scene_name=scene_name,
                            subject_area=segment.subject_area,
                        )
                    except Exception as fix_exc:
                        raise RuntimeError(
                            f"Auto-fix failed: {fix_exc}\nOriginal error: {render_exc}"
                        )
                else:
                    raise

            clip_ref = register_asset(
                clip_path, segment.id, "manim_clip", segment.prompt_hash
            )

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
            try:
                log_manim_failure(
                    video_id=segment.video_id,
                    segment_order=segment.order,
                    segment_id=segment.id,
                    error=str(exc),
                    code=segment.generated_code or "",
                )
            except Exception:
                pass  # never let logging break the render flow
            raise
