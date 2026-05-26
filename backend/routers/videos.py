"""
Video generation router.
Checks subject support via feature_flags table.
Full AnimLearn pipeline — no compromise on quality.
"""
import json
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from database import get_db
from services.tier_config import get_limit, video_supported_for
from services.prompt_builder import build_video_prompt
from services.manim import generate_manim_code_enhanced, fix_manim_colors, ensure_numpy_import, _trigger_video_generation

router = APIRouter(prefix="/api/videos", tags=["videos"])


class VideoRequest(BaseModel):
    prompt: str
    conversation_id: str | None = None
    message_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    subject: str | None = None
    language: str = "en"
    aspect_ratio: str = "16:9"


@router.post("/generate")
async def generate_video(req: VideoRequest, bg: BackgroundTasks):
    # ── 1. Subject gate ──────────────────────────────────────────────────────
    supported = await video_supported_for(req.subject)
    if not supported:
        subject_label = req.subject or "this subject"
        return {
            "supported": False,
            "subject": req.subject,
            "message": f"Video generation for {subject_label} is coming soon. We currently support Mathematics, Physics, and Chemistry.",
        }

    # ── 2. Credit check ──────────────────────────────────────────────────────
    tier = "anonymous"
    if req.user_id:
        async with get_db() as db:
            user = await db.fetchrow("SELECT tier FROM users WHERE id = $1", req.user_id)
        tier = user["tier"] if user else "free"

    max_secs = await get_limit(tier, "video_max_secs")
    await _check_video_credit(req.user_id, req.session_id, tier)

    # ── 3. Create video record ───────────────────────────────────────────────
    async with get_db() as db:
        video = await db.fetchrow("""
            INSERT INTO videos
              (user_id, session_id, conversation_id, message_id,
               prompt, status, max_duration, language, aspect_ratio, subject)
            VALUES ($1,$2,$3,$4,$5,'pending',$6,$7,$8,$9)
            RETURNING id
        """, req.user_id, req.session_id, req.conversation_id, req.message_id,
            req.prompt, max_secs, req.language, req.aspect_ratio, req.subject)

    video_id = video["id"]

    # ── 4. Run full AnimLearn pipeline in background ─────────────────────────
    bg.add_task(
        _generate_video_bg,
        video_id, req.prompt, req.user_id, req.subject, req.language, req.aspect_ratio
    )

    return {"supported": True, "video_id": video_id, "status": "pending"}


@router.get("/conversation/{conversation_id}")
async def get_conversation_videos(conversation_id: str):
    """
    Returns all videos linked to messages in a conversation.
    Used by the frontend to restore inline video status cards after page refresh.
    """
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, message_id, status, video_url, error_message
            FROM videos
            WHERE conversation_id = $1 AND message_id IS NOT NULL
            ORDER BY created_at DESC
        """, conversation_id)
    return [dict(r) for r in rows]


@router.get("/{video_id}/status")
async def get_video_status(video_id: int):
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT id, status, video_url, thumbnail_url, error_message,
                   duration_secs, max_duration, created_at,
                   transcript_markdown, verified_solution
            FROM videos WHERE id = $1
        """, video_id)
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")
    return dict(row)


@router.get("/user/{user_id}")
async def get_user_videos(user_id: str):
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, status, video_url, thumbnail_url, prompt, subject,
                   duration_secs, created_at
            FROM videos WHERE user_id = $1
            ORDER BY created_at DESC LIMIT 50
        """, user_id)
    return [dict(r) for r in rows]


async def _generate_video_bg(
    video_id: int,
    prompt: str,
    user_id: str | None,
    subject: str | None,
    language: str,
    aspect_ratio: str,
):
    """
    Full AnimLearn pipeline — verbatim.
    transcript → SVG → Manim code → critic loop → Cloud Run trigger
    """
    try:
        # Build depth-adjusted prompt based on student profile
        teaching_prompt = await build_video_prompt(prompt, user_id, subject)

        # Full pipeline — copied from AnimLearn (no changes)
        code_data = await generate_manim_code_enhanced(
            teaching_prompt, language, 60, aspect_ratio
        )
        code = fix_manim_colors(code_data["code"])
        code = ensure_numpy_import(code)
        svg_urls          = code_data.get("svg_urls") or {}
        transcript        = code_data.get("transcript_markdown", "")
        verified_solution = code_data.get("verified_solution", "")

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET generated_code = $1, scene_name = $2, status = 'queued',
                    transcript_markdown = $3, verified_solution = $4,
                    svg_urls = $5::jsonb, updated_at = NOW()
                WHERE id = $6
            """, code, code_data.get("scene_name", "MainScene"),
                transcript, verified_solution, json.dumps(svg_urls), video_id)

        _trigger_video_generation(video_id, svg_urls)

    except Exception as e:
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW()
                WHERE id = $2
            """, str(e), video_id)


async def _check_video_credit(user_id: str | None, session_id: str | None, tier: str):
    async with get_db() as db:
        if user_id:
            limit = await get_limit(tier, "videos_daily")
            if limit == -1:
                return
            count = await db.fetchval("""
                SELECT COUNT(*) FROM usage_events
                WHERE user_id = $1 AND event_type = 'video_generated'
                AND created_at > NOW() - INTERVAL '1 day'
            """, user_id)
            if count >= limit:
                raise HTTPException(status_code=429, detail="Daily video limit reached")
            await db.execute(
                "INSERT INTO usage_events (user_id, event_type) VALUES ($1, 'video_generated')",
                user_id
            )
        elif session_id:
            row = await db.fetchrow(
                "SELECT video_count FROM anonymous_sessions WHERE id = $1", session_id
            )
            limit = await get_limit("anonymous", "videos_total")
            if row and row["video_count"] >= limit:
                raise HTTPException(status_code=429, detail="session_limit_reached")
            await db.execute(
                "UPDATE anonymous_sessions SET video_count = video_count + 1 WHERE id = $1",
                session_id
            )
