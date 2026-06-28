"""
Worked examples / practice problems extracted from a concept's source chapter.
Captured for free during chapter upload (routers/courses.py::_create_chapter_from_pdf
asks the same extraction call for problems alongside concepts). Teachers can then,
per problem:
  - Solve it      — structured step-by-step text solution (Manim pipeline Stage 1)
  - Make a video  — full animated derivation (Manim pipeline Stage 1+2, Cloud Run)
  - Teach it differently — 2-3 alternate pedagogical framings, text only

  GET   /api/courses/concepts/{concept_id}/problems        — list (teacher)
  GET   /api/courses/problems/{problem_id}                 — single (lazy video sync)
  POST  /api/courses/problems/{problem_id}/solve
  POST  /api/courses/problems/{problem_id}/video
  POST  /api/courses/problems/{problem_id}/teach-differently
  PATCH /api/courses/problems/{problem_id}                 — {approved: bool}
"""
import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel

from database import get_db
from routers.auth import decode_jwt
from routers.courses import _require_teacher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/courses", tags=["concept-problems"])

_DONE_VIDEO_STATUSES = ("complete", "completed")


def _fmt_problem(p) -> dict:
    return {
        "id":              str(p["id"]),
        "problem_text":    p["problem_text"],
        "position":        p["position"],
        "solution_text":   p["solution_text"],
        "solution_status": p["solution_status"],
        "video_status":    p["video_status"],
        "alt_teaching":    p["alt_teaching"],
        "alt_status":      p["alt_status"],
        "error_message":   p["error_message"],
        "approved":        p["approved"],
    }


async def _sync_video_status(problem_id: str, video_job_id: int | None, video_status: str) -> dict:
    """Lazily pulls the linked videos row's status the same way concept/assignment videos do."""
    if video_status != "generating" or not video_job_id:
        return {"video_status": video_status, "video_stage": None, "video_url": None}

    async with get_db() as db:
        video = await db.fetchrow(
            "SELECT status, video_url, error_message FROM videos WHERE id = $1", video_job_id
        )
    if not video:
        return {"video_status": video_status, "video_stage": None, "video_url": None}

    if video["status"] in _DONE_VIDEO_STATUSES:
        async with get_db() as db:
            await db.execute(
                "UPDATE concept_problems SET video_status = 'ready' WHERE id = $1::uuid", problem_id
            )
        return {"video_status": "ready", "video_stage": None, "video_url": video["video_url"]}

    if video["status"] == "failed":
        async with get_db() as db:
            await db.execute(
                "UPDATE concept_problems SET video_status = 'failed', error_message = $1 WHERE id = $2::uuid",
                video["error_message"], problem_id,
            )
        return {"video_status": "failed", "video_stage": None, "video_url": None}

    return {"video_status": "generating", "video_stage": video["status"], "video_url": None}


@router.get("/concepts/{concept_id}/problems")
async def list_concept_problems(concept_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        rows = await db.fetch(
            "SELECT * FROM concept_problems WHERE concept_id = $1::uuid ORDER BY position", concept_id
        )

    result = []
    for p in rows:
        item = _fmt_problem(p)
        sync = await _sync_video_status(item["id"], p["video_job_id"], p["video_status"])
        item.update(sync)
        result.append(item)
    return result


@router.get("/concepts/{concept_id}/problems/approved")
async def list_approved_concept_problems(concept_id: str, authorization: str = Header(...)):
    """Student-facing read: only teacher-approved worked examples, with whatever's ready shown."""
    decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        rows = await db.fetch(
            "SELECT * FROM concept_problems WHERE concept_id = $1::uuid AND approved = true ORDER BY position",
            concept_id,
        )

    result = []
    for p in rows:
        item = _fmt_problem(p)
        sync = await _sync_video_status(item["id"], p["video_job_id"], p["video_status"])
        item.update(sync)
        result.append(item)
    return result


@router.get("/problems/{problem_id}")
async def get_concept_problem(problem_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        p = await db.fetchrow("SELECT * FROM concept_problems WHERE id = $1::uuid", problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    item = _fmt_problem(p)
    sync = await _sync_video_status(item["id"], p["video_job_id"], p["video_status"])
    item.update(sync)
    return item


@router.post("/problems/{problem_id}/solve")
async def solve_concept_problem(problem_id: str, bg: BackgroundTasks, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        p = await db.fetchrow("SELECT id, problem_text, solution_status FROM concept_problems WHERE id = $1::uuid", problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    if p["solution_status"] == "generating":
        raise HTTPException(409, "Already generating")

    async with get_db() as db:
        await db.execute(
            "UPDATE concept_problems SET solution_status = 'generating', error_message = NULL WHERE id = $1::uuid",
            problem_id,
        )
    bg.add_task(_solve_problem_bg, problem_id, p["problem_text"])
    return {"ok": True, "solution_status": "generating"}


async def _solve_problem_bg(problem_id: str, problem_text: str):
    from services.manim import generate_solution_only
    try:
        solution_data = await generate_solution_only(problem_text, "en", 60)
        async with get_db() as db:
            await db.execute("""
                UPDATE concept_problems
                SET solution_text = $1, solution_status = 'ready', error_message = NULL
                WHERE id = $2::uuid
            """, solution_data["verified_solution"], problem_id)
    except Exception as exc:
        logger.error("[concept_problem] %s solve failed: %s", problem_id, exc, exc_info=True)
        async with get_db() as db:
            await db.execute(
                "UPDATE concept_problems SET solution_status = 'failed', error_message = $1 WHERE id = $2::uuid",
                str(exc)[:2000], problem_id,
            )


@router.post("/problems/{problem_id}/video")
async def make_concept_problem_video(problem_id: str, bg: BackgroundTasks, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        p = await db.fetchrow(
            "SELECT id, problem_text, solution_text, video_status FROM concept_problems WHERE id = $1::uuid",
            problem_id,
        )
    if not p:
        raise HTTPException(404, "Problem not found")
    if p["video_status"] == "generating":
        raise HTTPException(409, "Already generating")

    async with get_db() as db:
        await db.execute(
            "UPDATE concept_problems SET video_status = 'generating', error_message = NULL WHERE id = $1::uuid",
            problem_id,
        )
    bg.add_task(_video_problem_bg, problem_id, p["problem_text"], p["solution_text"])
    return {"ok": True, "video_status": "generating"}


async def _video_problem_bg(problem_id: str, problem_text: str, existing_solution_text: str | None):
    from services.manim import (
        generate_solution_only, generate_manim_from_solution,
        fix_manim_colors, ensure_numpy_import, _trigger_video_generation,
    )

    video_id = None
    try:
        duration = 60
        if existing_solution_text:
            # Already solved — skip Stage 1, same shortcut used by the chat retry endpoint.
            solution_data = {
                "verified_solution":   existing_solution_text,
                "transcript_markdown": existing_solution_text,
                "video_script":        existing_solution_text,
                "subject":             "general",
                "tags":                [],
            }
        else:
            solution_data = await generate_solution_only(problem_text, "en", duration)
            async with get_db() as db:
                await db.execute(
                    "UPDATE concept_problems SET solution_text = $1, solution_status = 'ready' WHERE id = $2::uuid",
                    solution_data["verified_solution"], problem_id,
                )

        async with get_db() as db:
            video = await db.fetchrow("""
                INSERT INTO videos (prompt, subject, language, aspect_ratio, max_duration, status)
                VALUES ($1, $2, 'en', '16:9', $3, 'pending')
                RETURNING id
            """, problem_text, solution_data.get("subject") or "general", duration)
            video_id = video["id"]
            await db.execute(
                "UPDATE concept_problems SET video_job_id = $1 WHERE id = $2::uuid", video_id, problem_id
            )
            await db.execute(
                "UPDATE videos SET transcript_markdown = $1, verified_solution = $2, status = 'transcript_ready', updated_at = NOW() WHERE id = $3",
                solution_data["transcript_markdown"], solution_data["verified_solution"], video_id,
            )

        code_data = await asyncio.wait_for(
            generate_manim_from_solution(solution_data, "en", duration, "16:9"), timeout=900
        )
        code     = fix_manim_colors(code_data["code"])
        code     = ensure_numpy_import(code)
        svg_urls = code_data.get("svg_urls") or {}

        async with get_db() as db:
            await db.execute("""
                UPDATE videos SET generated_code = $1, scene_name = $2, svg_urls = $3::jsonb,
                                  status = 'queued', updated_at = NOW()
                WHERE id = $4
            """, code, code_data.get("scene_name", "MainScene"), json.dumps(svg_urls), video_id)

        logger.info("[concept_problem] %s: Manim code ready, triggering Cloud Run render (video %s)", problem_id, video_id)
        _trigger_video_generation(video_id, svg_urls)
        # concept_problems.video_status stays 'generating' — GET endpoints lazily sync from `videos`.

    except Exception as exc:
        logger.error("[concept_problem] %s video failed: %s", problem_id, exc, exc_info=True)
        async with get_db() as db:
            if video_id:
                await db.execute(
                    "UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW() WHERE id = $2",
                    str(exc)[:2000], video_id,
                )
            await db.execute(
                "UPDATE concept_problems SET video_status = 'failed', error_message = $1 WHERE id = $2::uuid",
                str(exc)[:2000], problem_id,
            )


@router.post("/problems/{problem_id}/teach-differently")
async def teach_differently(problem_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        p = await db.fetchrow("SELECT id, problem_text FROM concept_problems WHERE id = $1::uuid", problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")

    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": (
                "Give 2-3 distinct pedagogical approaches to teaching or solving this problem — "
                "e.g. an analogy-based explanation, a visual/diagram-based approach, and a "
                "real-world-application framing. Format as markdown with a short heading per approach.\n\n"
                f"PROBLEM:\n{p['problem_text']}"
            )}],
            max_tokens=1200,
            temperature=0.5,
        )
        alt_text = response.choices[0].message.content
        async with get_db() as db:
            await db.execute(
                "UPDATE concept_problems SET alt_teaching = $1, alt_status = 'ready', error_message = NULL WHERE id = $2::uuid",
                alt_text, problem_id,
            )
        return {"ok": True, "alt_teaching": alt_text, "alt_status": "ready"}
    except Exception as exc:
        logger.error("[concept_problem] %s teach-differently failed: %s", problem_id, exc, exc_info=True)
        async with get_db() as db:
            await db.execute(
                "UPDATE concept_problems SET alt_status = 'failed', error_message = $1 WHERE id = $2::uuid",
                str(exc)[:2000], problem_id,
            )
        raise HTTPException(500, "Generation failed — please retry")


class ApproveProblemRequest(BaseModel):
    approved: bool


@router.patch("/problems/{problem_id}")
async def approve_concept_problem(problem_id: str, req: ApproveProblemRequest, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        result = await db.execute(
            "UPDATE concept_problems SET approved = $1 WHERE id = $2::uuid", req.approved, problem_id
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "Problem not found")
    return {"ok": True, "approved": req.approved}
