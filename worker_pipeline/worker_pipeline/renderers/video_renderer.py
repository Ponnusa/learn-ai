"""
Video segment renderer — Veo (Gemini video generation), feature-flagged.

Rare and expensive by design (Veo bills per second of generated video — see
PROJECT SPEC non-goals: "stays opt-in/feature-flagged due to per-second
cost"). Unlike image_renderer.py there is no critic/retry loop here: retrying
an expensive Veo call to fix a quality issue isn't worth it for a single
cinematic cutaway. A single failed or slow attempt demotes the segment to
"image" and re-dispatches through ImageRenderer rather than failing the
lesson or retrying Veo itself.

Belt-and-suspenders ENABLE_VEO check: storyboard.py already prevents "video"
type segments from existing when the flag is off at storyboard-generation
time (see storyboard.py's _build_storyboard), but this renderer re-checks the
flag at render time too — a storyboard written while the flag was on must not
bypass a later flag flip, per the "enforce in code, not prompt text alone"
discipline used throughout this pipeline.

NOTE ON VERIFICATION: like image_renderer.py, the google-genai Veo call shape
below (client.models.generate_videos, polling via client.operations.get,
extracting the clip from operation.response.generated_videos[0].video) is
written from the documented SDK shape but UNVERIFIED against a live call —
this dev machine has no GEMINI_API_KEY and no google-genai installed.

Manual verification steps (deliberately not automated — this costs real
money per run):
  1. pip install google-genai
  2. export GEMINI_API_KEY=... ENABLE_VEO=true
  3. from pipeline.renderers.video_renderer import VideoRenderer
     from pipeline.schema import Segment
     seg = Segment(id="seg-0", order=0, type="video", target_duration_seconds=5,
                   subject_area="physics", narration_text="...",
                   generation_prompt="<cinematography-style prompt>")
     VideoRenderer().render(seg)
  4. Confirm seg.status == "rendered", seg.clip_url is a playable R2 URL, and
     check the Gemini API console for the actual dollar cost of that one call
     before running a second one.
"""
import logging
import os
import tempfile
import time
from typing import Optional

from .. import tts
from ..tts import voice_for_language
from ..asset_manifest import AssetRef, check_cache, compute_prompt_hash, register_asset
from ..compositor import concat_clips, extract_last_frame_local
from ..schema import Segment
from .base import Renderer
from .image_renderer import ImageRenderer, make_ken_burns_clip

logger = logging.getLogger(__name__)

VEO_MODEL = os.getenv("VEO_MODEL", "veo-3.1-lite-generate-preview")
VEO_TIMEOUT_SECONDS = int(os.getenv("VEO_TIMEOUT_SECONDS", "180"))
VEO_POLL_INTERVAL_SECONDS = 10

_genai_client = None


def _enable_veo() -> bool:
    return os.getenv("ENABLE_VEO", "false").strip().lower() in ("1", "true", "yes")


def _get_genai_client():
    global _genai_client
    if _genai_client is None:
        from google import genai
        _genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _genai_client


def build_video_prompt(segment: Segment) -> str:
    """
    storyboard.py already dialects generation_prompt as cinematography
    direction for video segments (camera framing, real-world motion) — this
    just reinforces the one hard constraint Veo needs repeated: no reliance
    on on-screen text, since narration carries the information instead.
    """
    return (
        f"{segment.generation_prompt}\n\n"
        "Do not include any on-screen text, captions, or labels — narration "
        "will be added separately as voiceover."
    )


def generate_veo_clip(prompt: str, output_path: str) -> None:
    """
    Kick off Veo generation and poll its long-running operation until done or
    VEO_TIMEOUT_SECONDS elapses. Raises TimeoutError/RuntimeError — never
    writes a placeholder file, so a caller can tell a real clip from a failure
    purely by whether this raised.
    """
    client = _get_genai_client()
    operation = client.models.generate_videos(model=VEO_MODEL, prompt=prompt)

    elapsed = 0
    while not operation.done:
        if elapsed >= VEO_TIMEOUT_SECONDS:
            raise TimeoutError(f"Veo generation exceeded {VEO_TIMEOUT_SECONDS}s — abandoning")
        time.sleep(VEO_POLL_INTERVAL_SECONDS)
        elapsed += VEO_POLL_INTERVAL_SECONDS
        operation = client.operations.get(operation)

    generated = getattr(operation.response, "generated_videos", None)
    if not generated:
        raise RuntimeError("Veo operation completed but returned no video")

    video_file = generated[0].video
    client.files.download(file=video_file)
    video_file.save(output_path)

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Veo output is missing or empty after download")


class VideoRenderer(Renderer):
    def __init__(self, image_renderer: Optional[ImageRenderer] = None, work_dir: Optional[str] = None):
        # Fallback path for disabled/failed/timed-out Veo — always constructed
        # so a demotion never fails for lack of somewhere to demote *to*.
        self._work_dir = work_dir or tempfile.gettempdir()
        self._image_renderer = image_renderer or ImageRenderer(work_dir=self._work_dir)

    def render(self, segment: Segment) -> AssetRef:
        if not _enable_veo():
            logger.info(f"[video_renderer] ENABLE_VEO is off — demoting segment {segment.id} to image")
            return self._demote_to_image(segment)

        segment.status = "generating"
        # clip_hash includes narration_text (unlike a bare prompt hash) since
        # the final clip's audio track depends on it — same reasoning as
        # image_renderer.py's image_hash/clip_hash split.
        clip_hash = compute_prompt_hash(
            f"{segment.generation_prompt}||{segment.narration_text}", "", f"{segment.subject_area}||{segment.language}",
        )
        segment.prompt_hash = clip_hash

        cached = check_cache(clip_hash, "video_clip", segment.id, ".mp4")
        if cached:
            logger.info(f"[video_renderer] cache hit for segment {segment.id} — skipping Veo call")
            segment.clip_url = cached.url
            segment.actual_duration_seconds = segment.target_duration_seconds
            segment.status = "rendered"
            return cached

        try:
            prompt = build_video_prompt(segment)
            raw_clip_path = os.path.join(self._work_dir, f"{segment.id}_veo_raw.mp4")
            generate_veo_clip(prompt, raw_clip_path)

            # Veo's own audio (if any) is replaced with narration entirely —
            # simpler than mixing two audio sources, and the narration is the
            # part that actually has to be there.
            audio_path = os.path.join(self._work_dir, f"{segment.id}_{clip_hash}_narration.wav")
            tts.generate_narration_audio(segment.narration_text, audio_path, voice_for_language(segment.language))

            # Veo returns clips at a fixed model duration (e.g. 6-8s) with no
            # relationship to how long the narration actually takes to speak.
            # mux_audio_onto_video()'s -shortest would otherwise silently
            # truncate narration mid-sentence if it runs longer than the raw
            # clip — instead, extend the visual by holding its last frame for
            # the gap (same trick orchestrator.py's degrade path uses when a
            # visual comes up short of its narration).
            narration_duration = tts.get_media_duration(audio_path)
            video_duration = tts.get_media_duration(raw_clip_path)
            if narration_duration > video_duration:
                gap = narration_duration - video_duration
                frame_path = os.path.join(self._work_dir, f"{segment.id}_last_frame.png")
                extract_last_frame_local(raw_clip_path, frame_path)
                hold_path = os.path.join(self._work_dir, f"{segment.id}_hold.mp4")
                make_ken_burns_clip(frame_path, gap, hold_path, segment.aspect_ratio)
                extended_path = os.path.join(self._work_dir, f"{segment.id}_extended.mp4")
                concat_clips([raw_clip_path, hold_path], extended_path, fade=False)
                raw_clip_path = extended_path
                logger.info(
                    f"[video_renderer] segment {segment.id}: narration ({narration_duration:.1f}s) "
                    f"exceeds Veo clip ({video_duration:.1f}s) — held last frame for {gap:.1f}s"
                )

            clip_path = os.path.join(self._work_dir, f"{segment.id}_{clip_hash}.mp4")
            tts.mux_audio_onto_video(raw_clip_path, audio_path, clip_path)

            clip_ref = register_asset(clip_path, segment.id, "video_clip", clip_hash)
            segment.clip_url = clip_ref.url
            segment.actual_duration_seconds = tts.get_media_duration(clip_path)
            segment.status = "rendered"
            segment.error_message = None
            logger.info(f"[video_renderer] segment {segment.id} rendered via Veo")
            return clip_ref

        except Exception as exc:
            logger.warning(
                f"[video_renderer] Veo failed for segment {segment.id} ({exc}) — demoting to image"
            )
            return self._demote_to_image(segment)

    def _demote_to_image(self, segment: Segment) -> AssetRef:
        segment.type = "image"
        return self._image_renderer.render(segment)
