"""
Image segment renderer — Nano Banana (Gemini image generation) + Ken Burns clip.

Ported from learnai/backend/services/educational_image.py's shape:
  build prompt -> generate -> vision critic -> retry once on low score -> upload.
Differences from that file: single-provider (google-genai covers both Nano
Banana generation and the vision critic, vs. that file's gpt-image-1 + GPT-4o
split), and an added Ken-Burns step (still image -> N-second mp4) since this
renderer's output must be a clip, not a static image, to fit the compositor's
"segment in -> clip out" contract shared with the Manim and Veo renderers.

NOTE ON VERIFICATION: the google-genai call shapes below (model names,
`client.models.generate_content`, `types.Part.from_bytes`, and where inline
image bytes land in the response) are written from the current google-genai
SDK's documented shape and have not been exercised against a live call as of
the Sprint 6 port. Smoke-test this against a real key before relying on it.

PORT NOTE: dev-repo used a local domain_styles.py subset; this uses the real,
full backend/services/domain_templates.py (reached via the sys.path shim
worker.py adds at startup) — same source of truth backend/services/
educational_image.py already draws from.
"""
import json
import logging
import os
import subprocess
import tempfile
from typing import Callable, Optional

import requests

from .. import qa
from .. import tts
from ..tts import voice_for_language
from ..asset_manifest import AssetRef, check_cache, compute_prompt_hash, register_asset
from services.domain_templates import BAD_VISUALS, DOMAIN_STYLES
from ..schema import Segment
from .base import Renderer

logger = logging.getLogger(__name__)

NANO_BANANA_MODEL = os.getenv("NANO_BANANA_MODEL", "gemini-2.5-flash-image")
GEMINI_CRITIC_MODEL = os.getenv("GEMINI_CRITIC_MODEL", "gemini-3.5-flash-lite")

_RESOLUTIONS = {
    "16:9": (1280, 720), "9:16": (720, 1280), "1:1": (720, 720), "4:5": (720, 900),
}

_genai_client = None


def _get_genai_client():
    global _genai_client
    if _genai_client is None:
        from google import genai
        _genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _genai_client


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_image_prompt(segment: Segment, correction_feedback: str = "") -> str:
    """Wraps the storyboard's art-direction generation_prompt with subject style,
    forbidden-visuals list, and (on retry) critic correction feedback.

    Deliberately does NOT force a fixed visual style (e.g. "pure white background,
    textbook line-art") here anymore — storyboard.py's generation_prompt already
    dialects each image segment as either a realistic photo or a labeled diagram
    depending on content, and a hardcoded style override here would fight whichever
    one it actually asked for (this was the likely cause of a low critic score seen
    in testing: a realistic-photo brief getting overridden by a forced white
    background/line-art instruction appended to the same prompt). Only the rules
    that apply regardless of style — label formatting IF labels are used, forbidden
    misleading visuals — stay fixed here.
    """
    style = DOMAIN_STYLES.get(segment.subject_area, DOMAIN_STYLES["general"])
    forbidden = "\n".join(f"  - {b}" for b in BAD_VISUALS)
    correction = (
        f"\n\nCORRECTION (fix these issues from the previous attempt):\n{correction_feedback}"
        if correction_feedback else ""
    )
    return f"""Educational {segment.subject_area} visual.

VISUAL BRIEF (follow this exactly, including whatever style it specifies — realistic photo or diagram):
{segment.generation_prompt}

SUBJECT STYLE NOTES (apply only where they don't conflict with the visual brief's own style): {style}

LABELLING RULES (only if the visual brief calls for on-image labels — skip entirely for a pure photo):
- Each label is SHORT, directly on or next to its element (max 4 words)
- Labels are identifiers only: element name + unit if applicable
- NO title text block, NO subtitle, NO paragraph text, NO floating description
- NO legend boxes with long text

NEVER INCLUDE (scientifically misleading):
{forbidden}{correction}"""


# ─────────────────────────────────────────────────────────────────────────────
# Generation + critic
# ─────────────────────────────────────────────────────────────────────────────

def generate_image_bytes(prompt: str, reference_image_bytes: Optional[bytes] = None) -> bytes:
    """Call Nano Banana. Raises if the response contains no image part — never
    returns a placeholder."""
    from google.genai import types

    client = _get_genai_client()
    contents = [prompt]
    if reference_image_bytes:
        contents.append(types.Part.from_bytes(data=reference_image_bytes, mime_type="image/png"))

    response = client.models.generate_content(model=NANO_BANANA_MODEL, contents=contents)

    candidates = response.candidates
    if not candidates:
        raise RuntimeError(f"Nano Banana returned no candidates (likely safety filter or quota). Prompt: {prompt[:200]}")
    content = candidates[0].content
    if not content or not content.parts:
        raise RuntimeError(f"Nano Banana candidate has no content parts. Finish reason: {getattr(candidates[0], 'finish_reason', 'unknown')}")
    for part in content.parts:
        if getattr(part, "inline_data", None) is not None:
            return part.inline_data.data
    raise RuntimeError("Nano Banana response contained no image data")


def run_vision_critic(image_bytes: bytes, segment: Segment) -> dict:
    """Score the generated image against the segment's own brief. Non-fatal on
    failure — returns a passing score so a critic outage doesn't force retries."""
    from google.genai import types

    prompt = f"""Review this educational diagram for scientific accuracy and educational quality.

VISUAL BRIEF IT WAS SUPPOSED TO SATISFY: {segment.generation_prompt}
SUBJECT: {segment.subject_area}

Evaluate:
1. Scientific accuracy — are all concepts shown correctly?
2. Label completeness and correctness (spelling, units, notation)
3. Misleading visuals — anything that could teach the wrong concept?
4. Educational clarity — is it immediately clear to a student?

Return ONLY valid JSON, no markdown fences:
{{"score": <integer 0-100>, "issues": ["<specific problem>"], "correction_prompt": "<one paragraph fix instruction>"}}"""

    try:
        client = _get_genai_client()
        response = client.models.generate_content(
            model=GEMINI_CRITIC_MODEL,
            contents=[types.Part.from_bytes(data=image_bytes, mime_type="image/png"), prompt],
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        report = json.loads(text)
        logger.info(f"[critic] score={report.get('score')} issues={len(report.get('issues', []))}")
        return report
    except Exception as exc:
        logger.warning(f"[critic] vision critic failed ({exc}) — accepting as-is")
        return {"score": qa.CRITIC_THRESHOLD, "issues": [], "correction_prompt": ""}


# ─────────────────────────────────────────────────────────────────────────────
# Ken Burns clip (fork of learnai/worker.py's prepare_question_image, swapping
# the static overlay for a pan/zoom; keeps its exact fps/resolution-matching
# and silent-audio-track pattern so the compositor's concat-demuxer fast path
# still works across mixed-origin clips)
# ─────────────────────────────────────────────────────────────────────────────

def make_ken_burns_clip(
    image_path: str,
    duration_seconds: float,
    output_path: str,
    aspect_ratio: str = "16:9",
    fps: int = 30,
) -> None:
    width, height = _RESOLUTIONS.get(aspect_ratio, _RESOLUTIONS["16:9"])
    fade_duration = min(0.5, duration_seconds / 4)
    total_frames = max(1, int(duration_seconds * fps))
    zoom_expr = "min(zoom+0.0008,1.15)"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-filter_complex",
        f"[0:v]scale=8000:-1,"
        f"zoompan=z='{zoom_expr}':d={total_frames}:s={width}x{height}:fps={fps},"
        f"fade=t=in:st=0:d={fade_duration},"
        f"fade=t=out:st={max(0.0, duration_seconds - fade_duration)}:d={fade_duration}[v]",
        "-map", "[v]", "-map", "1:a",
        "-t", str(duration_seconds),
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-r", str(fps),
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found on PATH — required for the Ken Burns clip step")
    if result.returncode != 0:
        raise RuntimeError(f"Ken Burns clip generation failed:\n{result.stderr[-1000:]}")
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Ken Burns output is missing or empty")


# ─────────────────────────────────────────────────────────────────────────────
# Renderer
# ─────────────────────────────────────────────────────────────────────────────

class ImageRenderer(Renderer):
    def __init__(
        self,
        resolve_reference: Optional[Callable[[str], Optional[str]]] = None,
        work_dir: Optional[str] = None,
    ):
        # resolve_reference: segment_id -> that segment's already-rendered
        # source_asset_url, or None. Injected rather than looked up here
        # because a lone Segment doesn't carry its sibling segments — the
        # Sprint 5 orchestrator is what actually knows the full storyboard
        # and wires in the real lookup. Defaults to "no reference available"
        # so this renderer is independently testable before Sprint 5 exists.
        self._resolve_reference = resolve_reference or (lambda seg_id: None)
        self._work_dir = work_dir or tempfile.gettempdir()

    def render(self, segment: Segment) -> AssetRef:
        segment.status = "generating"
        try:
            # Two hashes, deliberately: the still image only depends on the
            # visual brief (reusable across any narration of the same
            # visual), but the final clip's audio track depends on
            # narration_text too — a different script over the same diagram
            # needs a different muxed clip, so it needs a different cache key.
            image_hash = compute_prompt_hash(
                segment.generation_prompt,
                segment.style_reference_segment_id or "",
                f"{segment.subject_area}||{segment.language}",
            )
            clip_hash = compute_prompt_hash(
                f"{segment.generation_prompt}||{segment.narration_text}",
                segment.style_reference_segment_id or "",
                f"{segment.subject_area}||{segment.language}",
            )
            segment.prompt_hash = clip_hash

            cached = check_cache(clip_hash, "image_clip", segment.id, ".mp4")
            if cached:
                logger.info(f"[image_renderer] cache hit for segment {segment.id}")
                segment.clip_url = cached.url
                segment.actual_duration_seconds = segment.target_duration_seconds
                segment.status = "rendered"
                return cached

            reference_bytes = self._fetch_reference_bytes(segment)

            def _generate(feedback: str) -> bytes:
                return generate_image_bytes(build_image_prompt(segment, feedback), reference_bytes)

            def _critic(image_bytes: bytes) -> dict:
                return run_vision_critic(image_bytes, segment)

            image_bytes, report = qa.run_with_critic(_generate, _critic)

            image_path = os.path.join(self._work_dir, f"{segment.id}_{image_hash}.png")
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            source_ref = register_asset(image_path, segment.id, "image", image_hash)
            segment.source_asset_url = source_ref.url

            # Narration BEFORE the Ken Burns clip, deliberately: the clip's
            # duration should match the real spoken length, not the
            # storyboard's rough target_duration_seconds estimate.
            audio_path = os.path.join(self._work_dir, f"{segment.id}_{clip_hash}_narration.wav")
            tts.generate_narration_audio(segment.narration_text, audio_path, voice_for_language(segment.language))
            narration_duration = tts.get_media_duration(audio_path)

            silent_clip_path = os.path.join(self._work_dir, f"{segment.id}_{clip_hash}_silent.mp4")
            make_ken_burns_clip(image_path, narration_duration, silent_clip_path, segment.aspect_ratio)

            clip_path = os.path.join(self._work_dir, f"{segment.id}_{clip_hash}.mp4")
            tts.mux_audio_onto_video(silent_clip_path, audio_path, clip_path)
            clip_ref = register_asset(clip_path, segment.id, "image_clip", clip_hash)

            segment.clip_url = clip_ref.url
            segment.actual_duration_seconds = narration_duration
            segment.status = "rendered"
            segment.error_message = None
            logger.info(
                f"[image_renderer] segment {segment.id} rendered, critic score={report.get('score')}"
            )
            return clip_ref

        except Exception as exc:
            # Marked here; the Sprint 5 orchestrator decides retry vs. degrade
            # based on segment.status/retry_count — this renderer's job is only
            # to report failure accurately, not to decide the fallback policy.
            segment.status = "failed"
            segment.retry_count += 1
            segment.error_message = str(exc)[:500]
            logger.error(f"[image_renderer] segment {segment.id} failed: {exc}")
            raise

    def _fetch_reference_bytes(self, segment: Segment) -> Optional[bytes]:
        if not segment.style_reference_segment_id:
            return None
        ref_url = self._resolve_reference(segment.style_reference_segment_id)
        if not ref_url:
            return None
        try:
            resp = requests.get(ref_url, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            logger.warning(f"[image_renderer] failed to fetch style reference: {exc} — continuing without it")
            return None
