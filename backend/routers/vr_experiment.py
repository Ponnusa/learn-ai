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
from fastapi import APIRouter, HTTPException, Header

from database import get_db
from routers.admin import _require_super_admin

router = APIRouter(prefix="/api/admin/vr-experiment", tags=["vr-experiment"])


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

    return {
        "video_id": video["id"],
        "prompt": video["prompt"],
        "subject": video["subject"],
        "status": video["status"],
        "segments": [dict(s) for s in segments],
    }
