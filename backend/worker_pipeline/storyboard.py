"""
Storyboard generator — ported from manim-video-generator/backend/pipeline/storyboard.py.

Converts a lesson topic + verified solution into an ordered Storyboard of
typed segments (manim | image | video), each carrying a generation_prompt
already dialected for its target renderer (Manim direction / art-direction /
cinematography).

Structural bookkeeping (id, order, status, retry_count) is assigned in code
and never trusted from the LLM's JSON — only semantic content fields are
parsed from it. The enable_veo cap is enforced the same way: in code, not by
prompt wording alone, so a stale/adversarial LLM response can't smuggle extra
video segments through.

NOT CURRENTLY CALLED BY ANYTHING (as of the Sprint 6 port): nothing in the
product yet creates video_segments rows for a real request — that trigger is
a deliberate follow-up decision, not part of this port. This module exists so
the worker's rendering capability (which IS wired up) has something to
consume once a trigger is added.

PORT NOTE: dev-repo used a local domain_styles.py subset; this uses the real,
full backend/services/domain_templates.py (reached via the sys.path shim
worker.py adds at startup) so there's one source of truth for style guides,
shared with backend/services/educational_image.py.
"""
import json
import logging
from typing import Optional

from ._claude import MODEL as _MODEL
from ._claude import call_with_retry as _call_claude_with_retry
from services.domain_templates import DOMAIN_STYLES
from .schema import Segment, Storyboard

logger = logging.getLogger(__name__)

_MAX_VIDEO_SEGMENTS = 1
_MAX_PARSE_ATTEMPTS = 2


def _segment_budget(target_duration_seconds: int) -> int:
    return max(2, min(target_duration_seconds // 12, 15))


def _build_prompt(
    topic: str,
    verified_solution: str,
    subject_area: str,
    target_duration_seconds: int,
    enable_veo: bool,
    correction: str = "",
) -> str:
    style = DOMAIN_STYLES.get(subject_area, DOMAIN_STYLES["general"])
    num_segments = _segment_budget(target_duration_seconds)

    if enable_veo:
        video_rule = (
            f'At most {_MAX_VIDEO_SEGMENTS} segment may be type "video" — use it only for a rare '
            "cinematic hook or real-world cutaway, never for anything requiring on-screen text "
            "(video generation cannot reliably render legible text)."
        )
    else:
        video_rule = (
            'Do NOT use type "video" for any segment — video generation is disabled for this '
            'lesson. Use "image" instead for anything you would otherwise want as a cinematic cutaway.'
        )

    return f"""You are a lesson-video storyboard director for AnimLearn, an educational video
platform for Physics and Chemistry. Decompose the lesson below into an ordered list of
{num_segments} video segments.

LESSON TOPIC: {topic}
SUBJECT: {subject_area}
VERIFIED SOLUTION (do not re-derive or change any values):
{verified_solution}

TARGET TOTAL DURATION: {target_duration_seconds} seconds
STYLE GUIDE FOR THIS SUBJECT: {style}

Each segment has exactly one "type":
  - "manim" -> motion, derivations, processes, graphs — anything where change-over-time IS the
    pedagogy. generation_prompt must be Manim-direction style: exact object/animation intent
    (e.g. "GrowArrow for the normal force, perpendicular to the incline; ball moves along the
    slope with MoveAlongPath").
  - "image" -> a REALISTIC PHOTOGRAPH by default whenever the segment depicts a real-world
    object, scene, or scenario (e.g. a cup sweating with condensation, two materials side by
    side in daylight, someone demonstrating an everyday action). Photorealism is what
    differentiates an image segment from a manim segment and makes a lesson feel real rather
    than like a textbook slide. Only use a clean labeled-diagram style instead (structures,
    cross-sections, comparisons) when the content is inherently abstract/structural with no
    natural realistic depiction. Either way, generation_prompt must be pure art-direction:
    composition, what to show/label, lighting/style — NO Manim class names, NO code terms,
    NO camera-motion language (camera motion is video's job).
  - "video" -> {video_rule}
    generation_prompt (when used) must be cinematography style: camera framing and real-world
    motion — NEVER instruct on-screen text/labels.

Majority of segments should be "manim" or "image". Follow a Hook -> Build -> Reveal -> So-What
narrative arc across the ordered list.

For each segment provide:
  - draft_index: 0-based position in your list (must match array order)
  - type: "manim" | "image" | "video"
  - target_duration_seconds: number
  - narration_text: one sentence of narration for this segment (verbatim voiceover text)
  - generation_prompt: dialected per the rules above
  - style_reference_index: draft_index of an EARLIER segment in this same list whose generated
    visual should be used as a style/composition reference for this one, or null. Only set this
    for "image" segments that should visually match an earlier image (e.g. reusing a diagram
    style) — leave null otherwise.

Output ONLY valid JSON, no markdown fences, no explanation, in this exact shape:
{{"segments": [{{"draft_index": 0, "type": "manim", "target_duration_seconds": 8,
"narration_text": "...", "generation_prompt": "...", "style_reference_index": null}}]}}
{correction}"""


def _build_storyboard(
    lesson_id: str,
    subject_area: str,
    target_duration_seconds: int,
    draft_segments: list,
    enable_veo: bool,
    aspect_ratio: str = "16:9",
) -> Storyboard:
    # Sort by the LLM's own draft_index so downstream order is deterministic
    # even if the JSON array itself came back out of order.
    draft_segments = sorted(draft_segments, key=lambda d: d.get("draft_index", 0))

    video_count = 0
    segments: list[Segment] = []
    draft_index_to_id: dict = {}

    for order, draft in enumerate(draft_segments):
        seg_id = f"seg-{order}"
        this_draft_index = draft.get("draft_index", order)
        draft_index_to_id[this_draft_index] = seg_id

        seg_type = draft.get("type")
        if seg_type not in ("manim", "image", "video"):
            seg_type = "manim"  # never let an unrecognized type through unnoticed

        # Hard rule enforced in code: veo disabled or over cap -> demote to image.
        if seg_type == "video":
            if not enable_veo or video_count >= _MAX_VIDEO_SEGMENTS:
                seg_type = "image"
            else:
                video_count += 1

        ref_index = draft.get("style_reference_index")
        ref_id = None
        if (
            ref_index is not None
            and ref_index in draft_index_to_id
            and ref_index < this_draft_index
        ):
            ref_id = draft_index_to_id[ref_index]

        segments.append(Segment(
            id=seg_id,
            order=order,
            type=seg_type,
            target_duration_seconds=float(draft.get("target_duration_seconds", 8)),
            subject_area=subject_area,
            narration_text=draft.get("narration_text", ""),
            generation_prompt=draft.get("generation_prompt", ""),
            style_reference_segment_id=ref_id,
            aspect_ratio=aspect_ratio,
        ))

    return Storyboard(
        lesson_id=lesson_id,
        target_duration_seconds=target_duration_seconds,
        subject_area=subject_area,
        aspect_ratio=aspect_ratio,
        segments=segments,
    )


def generate_storyboard(
    lesson_id: str,
    topic: str,
    verified_solution: str,
    subject_area: str,
    target_duration_seconds: int,
    enable_veo: bool = False,
    aspect_ratio: str = "16:9",
) -> Storyboard:
    """
    Generate an ordered Storyboard of typed segments for a lesson.

    Raises ValueError if the LLM output can't be parsed/validated after one
    corrective retry — no silent fallback, matching the "fail loudly, never
    invent" discipline the rest of this pipeline follows for asset URLs.
    """
    correction = ""
    last_error: Optional[Exception] = None

    for attempt in range(1, _MAX_PARSE_ATTEMPTS + 1):
        prompt = _build_prompt(
            topic, verified_solution, subject_area, target_duration_seconds,
            enable_veo, correction,
        )
        raw = _call_claude_with_retry(
            model=_MODEL,
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
        )

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            draft_segments = parsed["segments"]
            if not draft_segments:
                raise ValueError("LLM returned an empty segments list")

            storyboard = _build_storyboard(
                lesson_id, subject_area, target_duration_seconds,
                draft_segments, enable_veo, aspect_ratio,
            )
            video_count = sum(1 for s in storyboard.segments if s.type == "video")
            logger.info(
                f"📋 Storyboard ready: {len(storyboard.segments)} segments ({video_count} video)"
            )
            return storyboard
        except Exception as exc:
            last_error = exc
            logger.warning(f"⚠️ Storyboard parse/validation failed (attempt {attempt}): {exc}")
            correction = (
                f"\n\nYour previous response failed with this error: {exc}\n"
                "Return ONLY the corrected JSON, matching the exact shape above."
            )

    raise ValueError(f"Storyboard generation failed after {_MAX_PARSE_ATTEMPTS} attempts: {last_error}")
