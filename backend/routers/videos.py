"""
Video generation router.
Checks subject support via feature_flags table.
Full AnimLearn pipeline — no compromise on quality.

Pipeline is split into two phases so the transcript is always saved,
even when Manim code generation fails:
  Phase 1 → GPT-4o solution + transcript  → status: transcript_ready
  Phase 2 → Claude Manim code + critic    → status: queued  (or failed)
"""
import json
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from database import get_db
from services.tier_config import get_limit, video_supported_for
from services.prompt_builder import build_video_prompt
from services.manim import (
    generate_manim_code_enhanced,
    generate_solution_only,
    generate_manim_from_solution,
    fix_manim_colors,
    ensure_numpy_import,
    _trigger_video_generation,
)

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

    # ── 4. Run pipeline in background (Phase 1 → Phase 2) ───────────────────
    bg.add_task(
        _generate_video_bg,
        video_id, req.prompt, req.user_id, req.subject, req.language, req.aspect_ratio
    )

    return {"supported": True, "video_id": video_id, "status": "pending"}


@router.post("/{video_id}/retry-manim")
async def retry_video_manim(video_id: int, bg: BackgroundTasks):
    """
    Re-run Manim code generation (Phase 2) using the already-saved transcript.
    Skips GPT-4o (Phase 1) — only retries the Manim/Claude/critic part.
    Requires transcript_markdown + verified_solution to already exist in DB.
    """
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT verified_solution, transcript_markdown, language, aspect_ratio, max_duration
            FROM videos WHERE id = $1
        """, video_id)

    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    if not row["verified_solution"]:
        raise HTTPException(
            status_code=400,
            detail="No transcript saved — please regenerate the full video instead.",
        )

    # Reset to pending so the frontend polls again
    async with get_db() as db:
        await db.execute("""
            UPDATE videos
            SET status = 'pending', error_message = NULL,
                generated_code = NULL, updated_at = NOW()
            WHERE id = $1
        """, video_id)

    solution_data = {
        "verified_solution":   row["verified_solution"],
        "transcript_markdown": row["transcript_markdown"] or "",
        "video_script":        row["transcript_markdown"] or "",
        "subject":             "general",
        "tags":                [],
    }

    bg.add_task(
        _retry_manim_bg,
        video_id, solution_data,
        row["language"] or "en",
        row["aspect_ratio"] or "16:9",
        row["max_duration"] or 60,
    )

    return {"status": "pending", "video_id": video_id}


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
                   transcript_markdown, verified_solution, prompt
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
                   duration_secs, created_at, transcript_markdown
            FROM videos WHERE user_id = $1
            ORDER BY created_at DESC LIMIT 50
        """, user_id)
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND TASKS
# ─────────────────────────────────────────────────────────────────────────────

async def _generate_video_bg(
    video_id: int,
    prompt: str,
    user_id: str | None,
    subject: str | None,
    language: str,
    aspect_ratio: str,
):
    """
    Two-phase pipeline:
    Phase 1 — GPT-4o solution → saves transcript immediately so it's never lost.
    Phase 2 — Claude Manim code → queues for rendering.
    If Phase 2 fails, video is 'failed' but transcript is already in the DB.
    """
    # ── Phase 1: solution + transcript ──────────────────────────────────────
    try:
        teaching_prompt = await build_video_prompt(prompt, user_id, subject)
        solution_data   = await generate_solution_only(teaching_prompt, language, 60)

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET transcript_markdown = $1, verified_solution = $2,
                    status = 'transcript_ready', updated_at = NOW()
                WHERE id = $3
            """, solution_data["transcript_markdown"],
                solution_data["verified_solution"], video_id)

    except Exception as e:
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW()
                WHERE id = $2
            """, f"Transcript generation failed: {e}", video_id)
        return

    # ── Phase 2: Manim code generation ──────────────────────────────────────
    try:
        code_data = await generate_manim_from_solution(
            solution_data, language, 60, aspect_ratio
        )
        code     = fix_manim_colors(code_data["code"])
        code     = ensure_numpy_import(code)
        svg_urls = code_data.get("svg_urls") or {}

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET generated_code = $1, scene_name = $2, status = 'queued',
                    svg_urls = $3::jsonb, updated_at = NOW()
                WHERE id = $4
            """, code, code_data.get("scene_name", "MainScene"),
                json.dumps(svg_urls), video_id)

        _trigger_video_generation(video_id, svg_urls)

    except Exception as e:
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW()
                WHERE id = $2
            """, f"Manim code generation failed: {e}", video_id)


async def _retry_manim_bg(
    video_id: int,
    solution_data: dict,
    language: str,
    aspect_ratio: str,
    duration: int,
):
    """Phase 2 only — used by the retry endpoint."""
    try:
        code_data = await generate_manim_from_solution(
            solution_data, language, duration, aspect_ratio
        )
        code     = fix_manim_colors(code_data["code"])
        code     = ensure_numpy_import(code)
        svg_urls = code_data.get("svg_urls") or {}

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET generated_code = $1, scene_name = $2, status = 'queued',
                    svg_urls = $3::jsonb, error_message = NULL, updated_at = NOW()
                WHERE id = $4
            """, code, code_data.get("scene_name", "MainScene"),
                json.dumps(svg_urls), video_id)

        _trigger_video_generation(video_id, svg_urls)

    except Exception as e:
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW()
                WHERE id = $2
            """, f"Manim retry failed: {e}", video_id)


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
