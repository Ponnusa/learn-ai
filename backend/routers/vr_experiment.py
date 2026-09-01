"""
VR/3D routing-plan experiment — read-only support endpoint.

Backs a standalone PowerShell script (scripts/vr-experiment-worker/run.ps1)
that classifies an existing video's Manim segments as flat-2D vs
3D-worthy-for-VR. This endpoint is the ONLY thing the experiment touches in
this codebase: a single SELECT, gated behind super-admin auth. Nothing here
writes to the database, the production render pipeline, or the asset
manifest — classification, LLM calls, and file output all happen locally in
the PowerShell script, outside this repo's runtime.
"""
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Header

from database import get_db
from routers.admin import _require_super_admin
from services.manim import r2_client, R2_BUCKET_NAME

router = APIRouter(prefix="/api/admin/vr-experiment", tags=["vr-experiment"])


def _refresh_r2_url(url: str | None) -> str | None:
    """video_segments.source_asset_url/clip_url are presigned URLs baked in
    at render time (1h expiry) — for a video rendered any time ago they're
    long dead. Re-sign from the same R2 key on every read instead of trusting
    the stored URL, so this experiment endpoint works on old videos too."""
    if not url or not r2_client:
        return url
    prefix = f"/{R2_BUCKET_NAME}/"
    path = urlparse(url).path
    if not path.startswith(prefix):
        return url
    key = path[len(prefix):]
    try:
        return r2_client.generate_presigned_url(
            "get_object", Params={"Bucket": R2_BUCKET_NAME, "Key": key}, ExpiresIn=3600,
        )
    except Exception:
        return url


@router.get("/video/{video_id}")
async def get_video_for_vr_experiment(video_id: int, authorization: str = Header(...)):
    await _require_super_admin(authorization)

    async with get_db() as db:
        video = await db.fetchrow(
            "SELECT id, prompt, subject, status FROM videos WHERE id = $1",
            video_id,
        )
        if not video:
            raise HTTPException(404, "Video not found")

        segments = await db.fetch(
            """
            SELECT segment_id, segment_order, type, target_duration_seconds,
                   actual_duration_seconds, subject_area, generation_prompt,
                   source_asset_url, clip_url, generated_code, status
            FROM video_segments
            WHERE video_id = $1
            ORDER BY segment_order
            """,
            video_id,
        )

    seg_dicts = []
    for s in segments:
        d = dict(s)
        d["source_asset_url"] = _refresh_r2_url(d["source_asset_url"])
        d["clip_url"] = _refresh_r2_url(d["clip_url"])
        seg_dicts.append(d)

    return {
        "video_id": video["id"],
        "prompt": video["prompt"],
        "subject": video["subject"],
        "status": video["status"],
        "segments": seg_dicts,
    }
