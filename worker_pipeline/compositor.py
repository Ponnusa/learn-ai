"""
Compositor — concatenates ordered segment clips into one final lesson mp4.

Extends learnai/worker.py's concat_videos() pattern almost exactly: concat
demuxer, stream-copy first, `ultrafast` re-encode fallback if the clips
aren't concat-compatible. Hard cuts only for v1 — no xfade/acrossfade
crossfades (per the sprint plan: precomputing offsets across N
heterogeneous-origin clips is real complexity not worth it until hard cuts
are proven; a hard cut between a Manim scene and a Ken-Burns pan already
reads fine pedagogically).

concat_clips() is the low-level, directly-testable primitive (local paths in,
local mp4 out). composite_segments() is the higher-level entry point that
downloads each segment's clip_url in order and hands local paths to
concat_clips() — this is the shape a Sprint 6 worker will actually call.
"""
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
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


def concat_clips(clip_paths: List[str], output_path: str) -> None:
    """
    Concatenate clip_paths, in the given order, into output_path.
    Raises on failure — never silently produces a partial/empty video.
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

    concat_list = os.path.join(tempfile.gettempdir(), f"compositor_concat_{uuid.uuid4().hex}.txt")
    temp_output = f"{output_path}.tmp.mp4"

    try:
        with open(concat_list, "w") as f:
            for path in clip_paths:
                f.write(f"file '{os.path.abspath(path)}'\n")

        logger.info(f"[compositor] concatenating {len(clip_paths)} clips (stream copy)...")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c", "copy", "-movflags", "+faststart", temp_output,
        ]
        result = _run_ffmpeg(cmd, timeout=30)

        if result.returncode != 0:
            logger.warning("[compositor] stream copy failed — re-encoding with ultrafast preset")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                "-movflags", "+faststart",
                "-force_key_frames", "expr:gte(t,n_forced*1)",
                temp_output,
            ]
            result = _run_ffmpeg(cmd, timeout=180)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg concatenation failed:\n{result.stderr[-1000:]}")

        if not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
            raise RuntimeError("Concatenated output is missing or empty")

        shutil.move(temp_output, output_path)
        logger.info(f"[compositor] composited {len(clip_paths)} clips -> {output_path}")

    finally:
        for tmp in (concat_list, temp_output):
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
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
