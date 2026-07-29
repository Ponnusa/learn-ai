"""
Video generation router.
Checks subject support via feature_flags table.
Full AnimLearn pipeline — no compromise on quality.

Pipeline is split into two phases so the transcript is always saved,
even when Manim code generation fails:
  Phase 1 → GPT-4o solution + transcript  → status: transcript_ready
  Phase 2 → Claude Manim code + critic    → status: queued  (or failed)
"""
import asyncio
import json
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from database import get_db
from services.tier_config import get_limit, video_supported_for
from services.prompt_builder import build_video_prompt
from services.subject_detector import detect_subject
from services.manim import (
    generate_manim_code_enhanced,
    generate_solution_only,
    generate_manim_from_solution,
    improve_manim_code,
    fix_manim_error,
    fix_manim_colors,
    fix_deprecated_manim_apis,
    fix_unicode_in_mathtex,
    ensure_numpy_import,
    strip_invalid_tex_weight,
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
    subject = req.subject
    # Auto-detect subject from prompt when not provided or not a recognised discipline
    if not subject or not await video_supported_for(subject):
        detected = await detect_subject(text=req.prompt)
        detected_sub = detected.get("subject")
        if detected_sub and await video_supported_for(detected_sub):
            subject = detected_sub

    supported = await video_supported_for(subject)
    if not supported:
        subject_label = subject or req.subject or "this subject"
        return {
            "supported": False,
            "subject": subject,
            "message": f"Video generation for {subject_label} is coming soon. We currently support Mathematics, Physics, and Chemistry.",
        }

    # ── 2. Credit check ──────────────────────────────────────────────────────
    tier = "anonymous"
    if req.user_id:
        async with get_db() as db:
            user = await db.fetchrow("SELECT tier FROM users WHERE id = $1::uuid", req.user_id)
        tier = user["tier"] if user else "free"

    max_secs = await get_limit(tier, "video_max_secs")
    await _check_video_credit(req.user_id, req.session_id, tier)

    # ── 3. Create video record ───────────────────────────────────────────────
    async with get_db() as db:
        video = await db.fetchrow("""
            INSERT INTO videos
              (user_id, session_id, conversation_id, message_id,
               prompt, status, max_duration, language, aspect_ratio, subject)
            VALUES ($1::uuid,$2::uuid,$3::uuid,$4::uuid,$5,'pending',$6,$7,$8,$9)
            RETURNING id
        """, req.user_id, req.session_id, req.conversation_id, req.message_id,
            req.prompt, max_secs, req.language, req.aspect_ratio, subject)

    video_id = video["id"]

    # ── 4. Run pipeline in background (Phase 1 → Phase 2) ───────────────────
    bg.add_task(
        _generate_video_bg,
        video_id, req.prompt, req.user_id, subject, req.language, req.aspect_ratio
    )

    return {"supported": True, "video_id": video_id, "status": "pending"}


@router.post("/{video_id}/retry-manim")
async def retry_video_manim(video_id: int, bg: BackgroundTasks):
    """
    Retry a failed video.
    - If verified_solution exists → Phase 2 only (skips GPT-4o, faster).
    - If not             → full pipeline using the saved prompt.
    """
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT verified_solution, transcript_markdown, language, aspect_ratio,
                   max_duration, prompt, user_id, subject
            FROM videos WHERE id = $1
        """, video_id)

    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    # Reset to pending so the frontend polls again
    async with get_db() as db:
        await db.execute("""
            UPDATE videos
            SET status = 'pending', error_message = NULL,
                generated_code = NULL, updated_at = NOW()
            WHERE id = $1
        """, video_id)

    lang        = row["language"]     or "en"
    ar          = row["aspect_ratio"] or "16:9"
    max_dur     = row["max_duration"] or 60

    if row["verified_solution"]:
        # Fast path — skip GPT-4o
        solution_data = {
            "verified_solution":   row["verified_solution"],
            "transcript_markdown": row["transcript_markdown"] or "",
            "video_script":        row["transcript_markdown"] or "",
            "subject":             row["subject"] or "general",   # use real subject, not "general"
            "tags":                [],
        }
        bg.add_task(_retry_manim_bg, video_id, solution_data, lang, ar, max_dur)
    else:
        # No transcript yet — run the full pipeline from the saved prompt
        prompt = row["prompt"] or ""
        uid    = str(row["user_id"]) if row["user_id"] else None
        bg.add_task(_generate_video_bg, video_id, prompt, uid, row["subject"], lang, ar)

    return {"status": "pending", "video_id": video_id}


@router.post("/{video_id}/regenerate")
async def regenerate_video(video_id: int, bg: BackgroundTasks):
    """Full regeneration — clears cached transcript/solution and reruns the entire pipeline."""
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT prompt, user_id, subject, language, aspect_ratio
            FROM videos WHERE id = $1
        """, video_id)
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    async with get_db() as db:
        await db.execute("""
            UPDATE videos
            SET status = 'pending', error_message = NULL,
                generated_code = NULL, transcript_markdown = NULL,
                verified_solution = NULL, updated_at = NOW()
            WHERE id = $1
        """, video_id)

    prompt = row["prompt"] or ""
    uid    = str(row["user_id"]) if row["user_id"] else None
    bg.add_task(
        _generate_video_bg, video_id, prompt, uid,
        row["subject"], row["language"] or "en", row["aspect_ratio"] or "16:9",
    )
    return {"status": "pending", "video_id": video_id}


class VideoImproveRequest(BaseModel):
    feedback: str


@router.post("/{video_id}/improve")
async def improve_video(video_id: int, req: VideoImproveRequest, bg: BackgroundTasks):
    """
    Feedback-driven improvement: re-generate Manim code using the original code as
    a base, applying user feedback about layout/animation issues.
    SVG data is preserved character-for-character by the AI prompt.
    """
    if not req.feedback.strip():
        raise HTTPException(status_code=422, detail="Feedback cannot be empty")

    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT generated_code, subject, language, aspect_ratio, user_id
            FROM videos WHERE id = $1
        """, video_id)
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")
    if not row["generated_code"]:
        raise HTTPException(status_code=409, detail="No generated code to improve — retry the video first")

    original_code = row["generated_code"]
    subject       = row["subject"]      or "general"
    language      = row["language"]     or "en"
    aspect_ratio  = row["aspect_ratio"] or "16:9"
    user_id       = str(row["user_id"]) if row["user_id"] else None

    # Log feedback for prompt improvement analysis
    async with get_db() as db:
        await db.execute("""
            INSERT INTO video_feedback (video_id, user_id, feedback, original_code)
            VALUES ($1, $2::uuid, $3, $4)
        """, video_id, user_id, req.feedback.strip(), original_code)

    # Reset to pending so the frontend can poll
    async with get_db() as db:
        await db.execute("""
            UPDATE videos
            SET status = 'pending', error_message = NULL,
                generated_code = NULL, updated_at = NOW()
            WHERE id = $1
        """, video_id)

    bg.add_task(
        _improve_video_bg,
        video_id, original_code, req.feedback.strip(),
        subject, language, aspect_ratio,
    )
    return {"status": "pending", "video_id": video_id}


async def _auto_fix_video_bg(
    video_id: int,
    original_code: str,
    error_message: str,
    subject: str,
    language: str,
    aspect_ratio: str,
    svg_urls: dict,
):
    """Phase 2.5: ask Claude to fix the render error, re-submit to Cloud Run."""
    logger = logging.getLogger(__name__)
    try:
        result = await asyncio.wait_for(
            fix_manim_error(original_code, error_message, subject, aspect_ratio, language),
            timeout=300,
        )
        code = fix_manim_colors(result["generated_code"])
        code = fix_unicode_in_mathtex(code)
        code = ensure_numpy_import(code)
        code = strip_invalid_tex_weight(code)

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET generated_code = $1, status = 'queued', error_message = NULL, updated_at = NOW()
                WHERE id = $2
            """, code, video_id)

        _trigger_video_generation(video_id, svg_urls)
        logger.info("[auto-fix] video %s fixed and re-queued", video_id)

    except asyncio.TimeoutError:
        logger.error("[auto-fix] video %s timed out after 5 min", video_id)
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'failed',
                    error_message = 'Auto-fix timed out — use Improve to describe what to fix',
                    updated_at = NOW()
                WHERE id = $1
            """, video_id)
    except Exception as exc:
        logger.error("[auto-fix] video %s failed: %s", video_id, exc)
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW()
                WHERE id = $2
            """, f"Auto-fix failed: {str(exc)[:1000]}", video_id)


@router.post("/{video_id}/auto-fix")
async def auto_fix_video(video_id: int, bg: BackgroundTasks):
    """
    Phase 2.5: pass the failed Manim code + renderer traceback to Claude,
    get a targeted error fix, and re-submit to Cloud Run.
    Faster than a full retry (no Phase 1 re-run) and handles most code-level
    errors: wrong API calls, bad LaTeX, off-screen coords, missing imports.
    """
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT generated_code, error_message, subject, language, aspect_ratio, svg_urls
            FROM videos WHERE id = $1
        """, video_id)

    if not row:
        raise HTTPException(404, "Video not found")
    if not row["generated_code"]:
        raise HTTPException(409, "No generated code to fix — run a full retry first")
    if not row["error_message"]:
        raise HTTPException(409, "Video has no error message to fix from")

    svg_urls: dict = {}
    if row["svg_urls"]:
        try:
            svg_urls = dict(row["svg_urls"]) if isinstance(row["svg_urls"], dict) else json.loads(row["svg_urls"])
        except Exception:
            pass

    async with get_db() as db:
        await db.execute(
            "UPDATE videos SET status = 'fixing', updated_at = NOW() WHERE id = $1",
            video_id,
        )

    bg.add_task(
        _auto_fix_video_bg,
        video_id,
        row["generated_code"],
        row["error_message"],
        row["subject"] or "general",
        row["language"] or "en",
        row["aspect_ratio"] or "16:9",
        svg_urls,
    )
    return {"status": "fixing", "video_id": video_id}


@router.delete("/{video_id}")
async def delete_video(video_id: int):
    async with get_db() as db:
        result = await db.execute("DELETE FROM videos WHERE id = $1", video_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Video not found")
    return {"deleted": True}


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
            WHERE conversation_id = $1::uuid
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
    """Returns all videos created by the user — any status, any source."""
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT v.id, v.status, v.video_url, v.thumbnail_url, v.prompt, v.subject,
                   v.duration_secs, v.created_at, v.transcript_markdown,
                   v.conversation_id, v.message_id, v.error_message,
                   cc.title  AS concept_title,
                   c.name    AS course_name
            FROM videos v
            LEFT JOIN course_concepts cc ON cc.id = v.concept_id
            LEFT JOIN course_units    cu ON cu.id = cc.unit_id
            LEFT JOIN courses          c ON c.id  = cu.course_id
            WHERE v.user_id = $1::uuid
               OR (v.concept_id IS NOT NULL AND c.teacher_id = $1::uuid)
            ORDER BY v.created_at DESC LIMIT 200
        """, user_id)
    return [dict(r) for r in rows]


@router.get("/session/{session_id}")
async def get_session_videos(session_id: str):
    """Completed videos for anonymous sessions (no user account)."""
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, status, video_url, thumbnail_url, prompt, subject,
                   duration_secs, created_at, transcript_markdown,
                   conversation_id, message_id
            FROM videos
            WHERE session_id = $1::uuid
              AND status IN ('complete', 'completed')
            ORDER BY created_at DESC LIMIT 200
        """, session_id)
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
    _log = logging.getLogger(__name__)
    _log.info(f"[pipeline] video {video_id}: starting full pipeline (Phase 1 + 2)")

    # ── Phase 1: solution + transcript ──────────────────────────────────────
    try:
        teaching_prompt = await build_video_prompt(prompt, user_id, subject, language)
        solution_data   = await generate_solution_only(teaching_prompt, language, 60)

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET transcript_markdown = $1, verified_solution = $2,
                    status = 'transcript_ready', updated_at = NOW()
                WHERE id = $3
            """, solution_data["transcript_markdown"],
                solution_data["verified_solution"], video_id)

        _log.info(f"[pipeline] video {video_id}: Phase 1 done → transcript_ready")

    except Exception as e:
        _log.error(f"[pipeline] video {video_id}: Phase 1 failed — {e}", exc_info=True)
        try:
            async with get_db() as db:
                await db.execute("""
                    UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW()
                    WHERE id = $2
                """, f"Transcript generation failed: {e}", video_id)
        except Exception as _db_err:
            _log.error(f"[pipeline] video {video_id}: also failed to write Phase 1 error — {_db_err}")
        return

    # ── Phase 2: Manim code generation ──────────────────────────────────────
    _log.info(f"[pipeline] video {video_id}: starting Phase 2 (Manim generation)")
    try:
        code_data = await asyncio.wait_for(
            generate_manim_from_solution(solution_data, language, 60, aspect_ratio),
            timeout=900,
        )
        code     = fix_manim_colors(code_data["code"])
        code     = fix_deprecated_manim_apis(code)
        code     = fix_unicode_in_mathtex(code)
        code     = ensure_numpy_import(code)
        code     = strip_invalid_tex_weight(code)
        svg_urls = code_data.get("svg_urls") or {}

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET generated_code = $1, scene_name = $2, status = 'queued',
                    svg_urls = $3::jsonb, updated_at = NOW()
                WHERE id = $4
            """, code, code_data.get("scene_name", "MainScene"),
                json.dumps(svg_urls), video_id)

        _log.info(f"[pipeline] video {video_id}: Phase 2 done → queued, triggering render")
        _trigger_video_generation(video_id, svg_urls)

    except asyncio.TimeoutError:
        _log.error(f"[pipeline] video {video_id}: Phase 2 timed out after 15 min")
        try:
            async with get_db() as db:
                await db.execute("""
                    UPDATE videos SET status = 'failed',
                        error_message = 'Manim generation timed out — please retry',
                        updated_at = NOW()
                    WHERE id = $1
                """, video_id)
        except Exception as _db_err:
            _log.error(f"[pipeline] video {video_id}: also failed to write timeout error — {_db_err}")
    except BaseException as e:
        # Catches Exception AND asyncio.CancelledError (BaseException subclass in Python 3.8+)
        # so Railway SIGTERM / event-loop shutdown never leaves a video stuck at transcript_ready.
        _log.error(f"[pipeline] video {video_id}: Phase 2 failed — {type(e).__name__}: {e}", exc_info=True)
        try:
            async with get_db() as db:
                await db.execute("""
                    UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW()
                    WHERE id = $2
                """, f"Manim code generation failed: {type(e).__name__}: {e}", video_id)
        except Exception as _db_err:
            _log.error(f"[pipeline] video {video_id}: also failed to write Phase 2 error — {_db_err}")
        if isinstance(e, asyncio.CancelledError):
            raise  # re-raise so the event loop can finish cleanup


async def _retry_manim_bg(
    video_id: int,
    solution_data: dict,
    language: str,
    aspect_ratio: str,
    duration: int,
):
    """Phase 2 only — used by the retry endpoint."""
    _log = logging.getLogger(__name__)
    _log.info(f"[retry] video {video_id}: starting Phase 2 (Manim generation)")

    # ── Immediately mark transcript_ready so the UI shows the correct step ──
    # (The transcript is already in the DB; we're only regenerating the Manim code.)
    try:
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'transcript_ready', updated_at = NOW()
                WHERE id = $1
            """, video_id)
    except Exception as _db_err:
        _log.warning(f"[retry] video {video_id}: could not set transcript_ready — {_db_err}")

    try:
        # Hard 15-minute deadline — each Claude call has a 120 s SDK timeout,
        # so 5 calls × 2 min = 10 min worst case; 15 min gives extra headroom.
        code_data = await asyncio.wait_for(
            generate_manim_from_solution(solution_data, language, duration, aspect_ratio),
            timeout=900,
        )
        code     = fix_manim_colors(code_data["code"])
        code     = fix_deprecated_manim_apis(code)
        code     = fix_unicode_in_mathtex(code)
        code     = ensure_numpy_import(code)
        code     = strip_invalid_tex_weight(code)
        svg_urls = code_data.get("svg_urls") or {}

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET generated_code = $1, scene_name = $2, status = 'queued',
                    svg_urls = $3::jsonb, error_message = NULL, updated_at = NOW()
                WHERE id = $4
            """, code, code_data.get("scene_name", "MainScene"),
                json.dumps(svg_urls), video_id)

        _log.info(f"[retry] video {video_id}: Manim code generated, triggering render")
        _trigger_video_generation(video_id, svg_urls)

    except asyncio.TimeoutError:
        _log.error(f"[retry] video {video_id}: Manim generation timed out after 15 min")
        try:
            async with get_db() as db:
                await db.execute("""
                    UPDATE videos SET status = 'failed',
                        error_message = 'Manim generation timed out — please retry',
                        updated_at = NOW()
                    WHERE id = $1
                """, video_id)
        except Exception as _db_err:
            _log.error(f"[retry] video {video_id}: also failed to write timeout error — {_db_err}")
    except BaseException as e:
        _log.error(f"[retry] video {video_id}: Manim generation failed — {type(e).__name__}: {e}", exc_info=True)
        try:
            async with get_db() as db:
                await db.execute("""
                    UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW()
                    WHERE id = $2
                """, f"Manim retry failed: {type(e).__name__}: {e}", video_id)
        except Exception as _db_err2:
            _log.error(f"[retry] video {video_id}: also failed to write error to DB — {_db_err2}")
        if isinstance(e, asyncio.CancelledError):
            raise


async def _check_video_credit(user_id: str | None, session_id: str | None, tier: str):
    async with get_db() as db:
        if user_id:
            limit = await get_limit(tier, "videos_daily")
            if limit == -1:
                return
            count = await db.fetchval("""
                SELECT COUNT(*) FROM usage_events
                WHERE user_id = $1::uuid AND event_type = 'video_generated'
                AND created_at > NOW() - INTERVAL '1 day'
            """, user_id)
            if count >= limit:
                raise HTTPException(status_code=429, detail="Daily video limit reached")
            await db.execute(
                "INSERT INTO usage_events (user_id, event_type) VALUES ($1::uuid, 'video_generated')",
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


async def _improve_video_bg(
    video_id: int,
    original_code: str,
    feedback: str,
    subject: str,
    language: str,
    aspect_ratio: str,
):
    """
    Background task for feedback-driven improvement.
    Calls Claude with the original code + feedback, then re-renders.
    """
    _log = logging.getLogger(__name__)
    _log.info(f"[improve] video {video_id}: starting feedback-driven improvement")

    try:
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'transcript_ready', updated_at = NOW()
                WHERE id = $1
            """, video_id)
    except Exception as _db_err:
        _log.warning(f"[improve] video {video_id}: could not set transcript_ready — {_db_err}")

    try:
        result = await asyncio.wait_for(
            improve_manim_code(original_code, feedback, subject, aspect_ratio, language),
            timeout=600,
        )
        code = result["generated_code"]
        code = fix_manim_colors(code)
        code = fix_deprecated_manim_apis(code)
        code = fix_unicode_in_mathtex(code)
        code = ensure_numpy_import(code)
        code = strip_invalid_tex_weight(code)

        # Preserve svg_urls from original video (SVG assets did not change)
        async with get_db() as db:
            original_svg = await db.fetchval("SELECT svg_urls FROM videos WHERE id = $1", video_id)
        svg_urls = json.loads(original_svg) if original_svg else {}

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET generated_code = $1, status = 'queued',
                    svg_urls = $2::jsonb, error_message = NULL, updated_at = NOW()
                WHERE id = $3
            """, code, json.dumps(svg_urls), video_id)

        _log.info(f"[improve] video {video_id}: code improved, triggering render")
        _trigger_video_generation(video_id, svg_urls)

    except asyncio.TimeoutError:
        _log.error(f"[improve] video {video_id}: timed out after 10 min")
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'failed',
                    error_message = 'Improvement timed out — please retry',
                    updated_at = NOW()
                WHERE id = $1
            """, video_id)
    except BaseException as e:
        _log.error(f"[improve] video {video_id}: failed — {type(e).__name__}: {e}", exc_info=True)
        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW()
                WHERE id = $2
            """, f"Improvement failed: {type(e).__name__}: {e}", video_id)
        if isinstance(e, asyncio.CancelledError):
            raise
