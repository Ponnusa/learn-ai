"""
Orchestrator — dispatches every segment in a Storyboard to the right renderer,
retries a failing segment once, and degrades to a held frame from the nearest
earlier rendered segment if it still fails, so one bad segment never sinks the
whole lesson.

Retry/degrade policy (formalizes the design discussion from planning):
  - Any segment type: retry the whole render() call once (MAX_RENDER_ATTEMPTS=2
    total attempts). This is a *failure* retry (API/network/ffmpeg errors) —
    distinct from image_renderer's own internal *quality* retry (low critic
    score), which already happened inside a single render() call.
  - video: Sprint 3's VideoRenderer already demotes Veo failures to image
    internally without raising. Orchestrator-level retry only engages if
    *both* Veo and that internal image demotion fail. On the second attempt,
    the renderer is re-looked-up by the segment's CURRENT type (see
    _render_with_degrade) rather than reusing the original video_renderer —
    otherwise a retry would re-attempt the expensive Veo call a second time
    even though attempt 1 already gave up on it and moved to image.
  - Any type, after exhausting retries: hold the nearest earlier rendered
    segment's last frame, re-narrated with this segment's OWN narration_text
    (via tts.py) so the viewer still hears what was meant to be said even
    though the intended visual failed, for the real spoken duration.
  - Edge case, deliberately NOT papered over: if the failing segment is first
    in the lesson (or every earlier segment also failed), there is no real
    frame to hold. Rather than fabricate a blank placeholder — which would
    violate the same "never invent an asset" discipline the URL guard
    enforces — this raises, surfacing the failure instead of silently
    shipping a broken lesson.
  - TTS is the one true hard-fail case (per the plan), and this falls out
    naturally rather than needing special-case code: the held-frame degrade
    path above ALSO calls tts.generate_narration_audio(). If Azure Speech is
    genuinely down, that call fails too, so the degrade path fails right
    along with the primary render, and the failure correctly propagates
    instead of shipping a mute segment.

Unified Manim codegen (pre-generation pass):
  Before the main render loop, _try_unified_manim_codegen() inspects all
  non-cached Manim segments. If there are 2+, it makes ONE Claude call
  (generate_all_manim_code) producing a single Python file with N scene
  classes and shared module-level constants (colors, font sizes, layout
  zones). The generated code and per-segment class name are stored on each
  Segment so ManimRenderer.render() can skip the per-segment Claude call.

  Benefits:
    - N→1 Claude API calls for a typical 3-segment lesson
    - Shared constants → visual consistency across segments

  Fall-back: any exception from the unified call is caught with a warning;
  segment.generated_code stays None so ManimRenderer falls back to per-
  segment generation exactly as it did before. Partial state (code set on
  some segments, not others) is cleared before returning.
"""
import logging
import os
import tempfile
import uuid
from typing import Callable, Dict, List, Optional

import requests

from . import tts
from .tts import voice_for_language
from .asset_manifest import compute_prompt_hash, register_asset
from .compositor import extract_last_frame_local
from .renderers.base import Renderer
from .renderers.image_renderer import ImageRenderer, make_ken_burns_clip
from .renderers.manim_renderer import (
    ManimRenderer,
    _check_manim_cache,
    _unified_class_name,
    generate_all_manim_code,
)
from .renderers.video_renderer import VideoRenderer
from .schema import Segment, Storyboard

logger = logging.getLogger(__name__)

MAX_RENDER_ATTEMPTS = 2


def _build_reference_resolver(storyboard: Storyboard) -> Callable[[str], Optional[str]]:
    by_id = {s.id: s for s in storyboard.segments}

    def resolve(segment_id: str) -> Optional[str]:
        seg = by_id.get(segment_id)
        return seg.source_asset_url if seg else None

    return resolve


def extract_last_frame(clip_url: str, output_path: str, work_dir: str) -> None:
    """Downloads clip_url and grabs its last frame via compositor.py's shared
    local-frame helper, mirroring learnai/worker.py's generate_thumbnail()."""
    local_clip = os.path.join(work_dir, f"_ref_{uuid.uuid4().hex}.mp4")
    resp = requests.get(clip_url, timeout=60)
    resp.raise_for_status()
    with open(local_clip, "wb") as f:
        f.write(resp.content)
    extract_last_frame_local(local_clip, output_path)


def _degrade_to_held_frame(
    segment: Segment, ordered_segments: List[Segment], work_dir: str, cause: Exception
) -> None:
    prior_rendered = [
        s for s in ordered_segments
        if s.order < segment.order and s.clip_url and s.status == "rendered"
    ]
    if not prior_rendered:
        raise RuntimeError(
            f"Segment {segment.id} failed after {MAX_RENDER_ATTEMPTS} attempts and has no "
            "earlier rendered segment to hold a frame from (it's first in the lesson, or every "
            f"earlier segment also failed) — cannot degrade further. Original error: {cause}"
        )
    reference_segment = prior_rendered[-1]  # closest earlier rendered segment

    frame_path = os.path.join(work_dir, f"{segment.id}_held_frame.png")
    extract_last_frame(reference_segment.clip_url, frame_path, work_dir)

    # The narration is the important part here, arguably more than the held
    # visual — a viewer should still hear what this segment was meant to say
    # even though its own visual failed. This also gives TTS the "hard-fail"
    # property described in tts.py's docstring: if Azure Speech is genuinely
    # down, this call fails too and the whole degrade path fails with it,
    # propagating instead of silently shipping a mute segment.
    prompt_hash = compute_prompt_hash(f"held-frame-from-{reference_segment.id}", "", segment.subject_area)
    audio_path = os.path.join(work_dir, f"{segment.id}_held_narration.wav")
    tts.generate_narration_audio(segment.narration_text, audio_path, voice_for_language(segment.language))
    narration_duration = tts.get_media_duration(audio_path)

    silent_clip_path = os.path.join(work_dir, f"{segment.id}_held_silent.mp4")
    make_ken_burns_clip(frame_path, narration_duration, silent_clip_path, segment.aspect_ratio)

    clip_path = os.path.join(work_dir, f"{segment.id}_held.mp4")
    tts.mux_audio_onto_video(silent_clip_path, audio_path, clip_path)
    clip_ref = register_asset(clip_path, segment.id, "held_frame_clip", prompt_hash)

    segment.clip_url = clip_ref.url
    segment.actual_duration_seconds = narration_duration
    segment.status = "rendered"
    segment.error_message = (
        f"Degraded: held frame from {reference_segment.id} after exhausting retries ({cause})"
    )[:500]
    logger.info(f"[orchestrator] segment {segment.id} degraded to held frame from {reference_segment.id}")


def _render_with_degrade(
    renderers: Dict[str, Renderer], segment: Segment, ordered_segments: List[Segment], work_dir: str
) -> None:
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RENDER_ATTEMPTS + 1):
        # Re-look-up by CURRENT type each attempt, not the type dispatched at
        # attempt 1 — a video segment that already demoted itself to image
        # internally (Sprint 3) must not re-attempt the expensive Veo call
        # on retry just because it was originally dispatched as "video".
        renderer = renderers[segment.type]
        try:
            renderer.render(segment)
            return
        except Exception as exc:
            last_exc = exc
            logger.warning(
                f"[orchestrator] segment {segment.id} attempt {attempt}/{MAX_RENDER_ATTEMPTS} failed: {exc}"
            )

    logger.warning(
        f"[orchestrator] segment {segment.id} exhausted {MAX_RENDER_ATTEMPTS} attempts — degrading"
    )
    _degrade_to_held_frame(segment, ordered_segments, work_dir, last_exc)


def _try_unified_manim_codegen(ordered_segments: List[Segment]) -> None:
    """
    Pre-generation pass: one Claude call to generate all non-cached Manim
    segments as a single Python file with N scene classes + shared constants.

    Populates segment.generated_code and segment.generated_class_name on each
    non-cached Manim segment so ManimRenderer.render() can skip its per-
    segment Claude call entirely.

    Skips if fewer than 2 Manim segments need generation (the per-segment
    path is already optimal for 0 or 1 segments). On any exception, clears
    partial state and logs a warning — ManimRenderer falls back to per-segment
    generation automatically when generated_code is None.
    """
    manim_segs = [s for s in ordered_segments if s.type == "manim"]
    if not manim_segs:
        return

    # Identify which segments are cache misses (need codegen at all).
    # _check_manim_cache also sets segment.prompt_hash as a side effect, so
    # ManimRenderer.render() can call register_asset without recomputing it.
    uncached = [s for s in manim_segs if _check_manim_cache(s) is None]

    if len(uncached) < 2:
        # 0 or 1 segment needs generation — unified path offers no saving.
        logger.info(
            f"[orchestrator] skipping unified Manim codegen "
            f"({len(uncached)} non-cached segment(s) — threshold is 2)"
        )
        return

    logger.info(
        f"[orchestrator] unified Manim codegen for {len(uncached)} segment(s): "
        + ", ".join(str(s.order) for s in uncached)
    )
    try:
        shared_code = generate_all_manim_code(uncached)
        for seg in uncached:
            seg.generated_code = shared_code
            seg.generated_class_name = _unified_class_name(seg)
        logger.info(
            f"[orchestrator] unified codegen done — "
            f"{len(uncached)} segments will skip per-segment Claude calls"
        )
    except Exception as exc:
        logger.warning(
            f"[orchestrator] unified Manim codegen failed ({exc}) — "
            "clearing partial state, falling back to per-segment generation"
        )
        # Clear any partial assignments so ManimRenderer gets a clean slate.
        for seg in uncached:
            seg.generated_code = None
            seg.generated_class_name = None


def render_storyboard(
    storyboard: Storyboard,
    work_dir: Optional[str] = None,
    renderers: Optional[Dict[str, Renderer]] = None,
) -> Storyboard:
    """
    Render every segment in a Storyboard, in order, applying the retry +
    degrade policy above. Mutates and returns the same Storyboard — segments
    are mutated in place by each renderer's render(), per the Renderer
    contract (base.py).

    `renderers` is injectable (segment type -> Renderer) so tests can supply
    fakes without needing real API keys/Docker; defaults to the real
    Manim/Image/Video renderers wired together with a live reference resolver.
    """
    work_dir = work_dir or tempfile.mkdtemp(prefix="orchestrator_")
    os.makedirs(work_dir, exist_ok=True)

    if renderers is None:
        resolve_reference = _build_reference_resolver(storyboard)
        image_renderer = ImageRenderer(resolve_reference=resolve_reference, work_dir=work_dir)
        renderers = {
            "manim": ManimRenderer(work_dir=work_dir),
            "image": image_renderer,
            "video": VideoRenderer(image_renderer=image_renderer, work_dir=work_dir),
        }

    ordered = sorted(storyboard.segments, key=lambda s: s.order)

    # Unified Manim pre-generation: one Claude call for all non-cached Manim
    # segments. Falls back to per-segment if this raises.
    _try_unified_manim_codegen(ordered)

    for segment in ordered:
        _render_with_degrade(renderers, segment, ordered, work_dir)

    return storyboard
