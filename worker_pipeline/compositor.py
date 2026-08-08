"""
Compositor — concatenates ordered segment clips into one final lesson mp4.

Originally mirrored learnai/worker.py's concat_videos() pattern (stream-copy
first, re-encode fallback only on a hard ffmpeg failure). That pattern is
safe for worker.py's own use (clips always come from one consistent
toolchain — the same Manim/Docker render, or a question-intro image built by
the same function). It is NOT safe here: this compositor concatenates clips
from three genuinely different origins (Manim's own render, our ffmpeg-muxed
Ken Burns/TTS clips, downloaded Veo output), which can have mismatched audio
parameters (sample rate, channel layout, codec profile). A stream-copy concat
across mismatched audio doesn't reliably fail loudly — it can exit 0 while
silently dropping or corrupting audio for some segments, which is exactly
what happened in testing (narration missing on some segments, present on
others, no error).

Fix: always decode and re-encode every stream through an explicit filter
graph that normalizes video (scale/pad to one resolution, fixed fps) and
audio (fixed sample rate/channel layout) before concatenating — no
stream-copy fast path. Slower, but this only runs once per lesson, and
correctness matters far more than shaving a few seconds here. Hard cuts only
(no xfade/acrossfade crossfades) — unchanged from the original design.

concat_clips() is the low-level, directly-testable primitive (local paths in,
local mp4 out). composite_segments() is the higher-level entry point that
downloads each segment's clip_url in order and hands local paths to
concat_clips().
"""
import logging
import os
import shutil
import subprocess
import tempfile
from typing import List, Optional

import requests

from .schema import Segment

logger = logging.getLogger(__name__)


def _run_ffmpeg(cmd: List[str], timeout: int) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found on PATH — required for compositing")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg concatenation timed out after {timeout}s")


def _probe_video_dims(path: str) -> tuple:
    """Returns (width, height, fps) of the first clip, used as the common
    target every clip gets normalized to before concatenation."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "csv=p=0", path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found on PATH — required for compositing")
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Failed to probe video dimensions for {path}: {result.stderr}")
    width_str, height_str, fps_str = result.stdout.strip().split(",")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = int(round(int(num) / max(int(den), 1)))
    else:
        fps = int(round(float(fps_str)))
    return int(width_str), int(height_str), max(fps, 1)


def concat_clips(clip_paths: List[str], output_path: str) -> None:
    """
    Concatenate clip_paths, in the given order, into output_path.
    Raises on failure — never silently produces a partial/empty video.

    Always re-encodes through a filter graph that normalizes every clip's
    video (scale/pad to match the first clip's resolution, fixed fps) and
    audio (fixed sample rate/channel layout) before concatenating — see
    module docstring for why a stream-copy fast path isn't safe here.
    """
    if not clip_paths:
        raise ValueError("No clips to concatenate")

    for path in clip_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Clip not found: {path}")

    if len(clip_paths) == 1:
        shutil.copy2(clip_paths[0], output_path)
        logger.info("[compositor] single clip — copied directly, no concat needed")
        return

    width, height, fps = _probe_video_dims(clip_paths[0])
    logger.info(f"[compositor] normalizing {len(clip_paths)} clips to {width}x{height}@{fps}fps")

    temp_output = f"{output_path}.tmp.mp4"
    try:
        inputs: List[str] = []
        filter_parts: List[str] = []
        concat_refs = ""
        for i, path in enumerate(clip_paths):
            inputs += ["-i", path]
            filter_parts.append(
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]"
            )
            filter_parts.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]")
            concat_refs += f"[v{i}][a{i}]"
        filter_complex = ";".join(filter_parts) + ";" + concat_refs + f"concat=n={len(clip_paths)}:v=1:a=1[outv][outa]"

        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-movflags", "+faststart",
            temp_output,
        ]
        result = _run_ffmpeg(cmd, timeout=max(180, 30 * len(clip_paths)))
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat filter failed:\n{result.stderr[-1500:]}")

        if not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
            raise RuntimeError("Concatenated output is missing or empty")

        shutil.move(temp_output, output_path)
        logger.info(f"[compositor] composited {len(clip_paths)} clips -> {output_path}")

    finally:
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass


def _download(url: str, dest: str) -> None:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)


def composite_segments(segments: List[Segment], output_path: str, work_dir: Optional[str] = None) -> None:
    """
    Downloads each segment's clip_url (sorted by `order`) and concatenates
    them into one final lesson mp4.

    Raises if any segment lacks a clip_url — a lesson can't be composited
    with a hole in it. Making sure every segment HAS some clip_url (even a
    held-frame fallback for a failed one) is the Sprint 5 orchestrator's job,
    not this function's.
    """
    work_dir = work_dir or tempfile.mkdtemp(prefix="compositor_")
    os.makedirs(work_dir, exist_ok=True)
    ordered = sorted(segments, key=lambda s: s.order)

    local_paths = []
    for seg in ordered:
        if not seg.clip_url:
            raise ValueError(f"Segment {seg.id} has no clip_url — cannot composite")
        local_path = os.path.join(work_dir, f"{seg.id}.mp4")
        _download(seg.clip_url, local_path)
        local_paths.append(local_path)

    concat_clips(local_paths, output_path)
