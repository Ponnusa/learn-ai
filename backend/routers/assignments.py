"""
Differentiated, per-student assignments — quiz / flashcards / study set / video
targeted at one struggling student instead of the whole classroom. Reuses the
existing generation pipelines (courses.py's quiz/flashcard prompt builders, the
Manim concept-video pipeline) rather than duplicating them.

  POST /api/assignments                     — teacher creates one (kicks off generation)
  GET  /api/assignments/student/{id}         — teacher: list a student's assignments
  GET  /api/assignments/mine                  — student: list my assignments
  GET  /api/assignments/{id}                  — fetch one (lazily syncs video status)
"""
import asyncio
import json
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel

from database import get_db
from routers.classrooms import _get_user
from routers.courses import (
    _get_student, build_quiz_prompt, build_flashcard_prompt,
    _map_manim_subject, _build_concept_video_prompt,
)
from routers.students import _require_teacher_of_student

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assignments", tags=["assignments"])

_KINDS = ("quiz", "flashcards", "video", "studyset")
_TEACHER_TYPES = ("teacher", "institution_admin", "super_admin")


class CreateAssignmentRequest(BaseModel):
    student_id: str
    concept_id: str
    kind: str


@router.post("")
async def create_assignment(
    req: CreateAssignmentRequest, bg: BackgroundTasks, authorization: str = Header(...)
):
    if req.kind not in _KINDS:
        raise HTTPException(400, f"kind must be one of {_KINDS}")

    teacher_id = await _require_teacher_of_student(authorization, req.student_id)

    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.title, cc.ai_summary, cc.ai_transcript, cc.source_text,
                   c.subject, c.teacher_id
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id = cu.course_id
            WHERE cc.id = $1::uuid
        """, req.concept_id)
    if not concept or str(concept["teacher_id"]) != teacher_id:
        raise HTTPException(404, "Concept not found")

    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO student_assignments (teacher_id, student_id, concept_id, kind, title, status)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, 'generating')
            RETURNING id
        """, teacher_id, req.student_id, req.concept_id, req.kind, concept["title"])
    assignment_id = str(row["id"])

    bg.add_task(_generate_assignment_bg, assignment_id, req.kind, dict(concept), req.student_id)
    return {"id": assignment_id, "status": "generating"}


@router.get("/student/{student_id}")
async def list_assignments_for_student(student_id: str, authorization: str = Header(...)):
    await _require_teacher_of_student(authorization, student_id)
    return await _list_assignments(student_id)


@router.get("/mine")
async def list_my_assignments(authorization: str = Header(...)):
    student_id = await _get_student(authorization)
    return await _list_assignments(student_id)


async def _list_assignments(student_id: str):
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, concept_id, kind, title, status, created_at
            FROM student_assignments WHERE student_id = $1::uuid
            ORDER BY created_at DESC
        """, student_id)
    return [
        {
            "id":         str(r["id"]),
            "concept_id": str(r["concept_id"]) if r["concept_id"] else None,
            "kind":       r["kind"],
            "title":      r["title"],
            "status":     r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


@router.get("/{assignment_id}")
async def get_assignment(assignment_id: str, authorization: str = Header(...)):
    caller_id, account_type = await _get_user(authorization)
    is_teacher = account_type in _TEACHER_TYPES

    async with get_db() as db:
        a = await db.fetchrow("SELECT * FROM student_assignments WHERE id = $1::uuid", assignment_id)
    if not a:
        raise HTTPException(404, "Assignment not found")

    owns = (is_teacher and str(a["teacher_id"]) == caller_id) or (not is_teacher and str(a["student_id"]) == caller_id)
    if not owns:
        raise HTTPException(403, "Not your assignment")

    status, error_message, video_stage, video_url = a["status"], a["error_message"], None, None

    # Video assignments render asynchronously on Cloud Run, which writes directly
    # to `videos` — sync that result here, same lazy pattern as get_concept_assets.
    if a["kind"] == "video" and a["video_job_id"] and status == "generating":
        async with get_db() as db:
            video = await db.fetchrow(
                "SELECT status, video_url, error_message FROM videos WHERE id = $1", a["video_job_id"]
            )
        if video:
            if video["status"] in ("complete", "completed"):
                status, video_url = "ready", video["video_url"]
                async with get_db() as db:
                    await db.execute(
                        "UPDATE student_assignments SET status = 'ready', completed_at = NOW() WHERE id = $1::uuid",
                        assignment_id,
                    )
            elif video["status"] == "failed":
                status, error_message = "failed", video["error_message"]
                async with get_db() as db:
                    await db.execute(
                        "UPDATE student_assignments SET status = 'failed', error_message = $1 WHERE id = $2::uuid",
                        error_message, assignment_id,
                    )
            else:
                video_stage = video["status"]  # pending|transcript_ready|queued|rendering
    elif a["kind"] == "video" and status == "ready":
        async with get_db() as db:
            video = await db.fetchrow("SELECT video_url FROM videos WHERE id = $1", a["video_job_id"])
        video_url = video["video_url"] if video else None

    return {
        "id":            str(a["id"]),
        "kind":          a["kind"],
        "title":         a["title"],
        "status":        status,
        "error_message": error_message,
        "video_stage":   video_stage,
        "video_url":     video_url,
        "payload":       a["payload"],
        "study_set_id":  str(a["study_set_id"]) if a["study_set_id"] else None,
    }


# ── Background generation ────────────────────────────────────────────────────

async def _generate_assignment_bg(assignment_id: str, kind: str, concept: dict, student_id: str):
    try:
        async with get_db() as db:
            profile = await db.fetchrow(
                "SELECT struggle_areas, known_misconceptions FROM student_profiles WHERE user_id = $1::uuid",
                student_id,
            )
        weak_spots = [*(profile["struggle_areas"] or []), *(profile["known_misconceptions"] or [])] if profile else []
        extra = (
            f"This student is struggling with: {', '.join(weak_spots[:5])}. "
            "Emphasize and reinforce these specific weak areas.\n"
            if weak_spots else ""
        )

        source  = concept["source_text"] or concept["ai_summary"] or concept["title"]
        subject = concept["subject"] or "General"

        if kind == "quiz":
            await _generate_assignment_quiz(assignment_id, concept["title"], subject, source, extra)
        elif kind == "flashcards":
            await _generate_assignment_flashcards(assignment_id, concept["title"], source, extra)
        elif kind == "studyset":
            await _generate_assignment_studyset(assignment_id, student_id, concept, subject, source)
        elif kind == "video":
            await _generate_assignment_video(assignment_id, concept, subject, extra)

    except Exception as exc:
        logger.error("[assignment] %s (%s) failed: %s", assignment_id, kind, exc, exc_info=True)
        async with get_db() as db:
            await db.execute(
                "UPDATE student_assignments SET status = 'failed', error_message = $1 WHERE id = $2::uuid",
                str(exc)[:2000], assignment_id,
            )


async def _generate_assignment_quiz(assignment_id: str, title: str, subject: str, source: str, extra: str):
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": build_quiz_prompt(title, subject, source, extra)}],
        response_format={"type": "json_object"},
        max_tokens=3000,
        temperature=0.3,
    )
    questions = json.loads(response.choices[0].message.content).get("questions", [])

    async with get_db() as db:
        await db.execute(
            "UPDATE student_assignments SET payload = $1::jsonb, status = 'ready', completed_at = NOW() WHERE id = $2::uuid",
            json.dumps(questions), assignment_id,
        )


async def _generate_assignment_flashcards(assignment_id: str, title: str, source: str, extra: str):
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": build_flashcard_prompt(title, source, extra)}],
        response_format={"type": "json_object"},
        max_tokens=2500,
        temperature=0.3,
    )
    cards = json.loads(response.choices[0].message.content).get("flashcards", [])

    async with get_db() as db:
        await db.execute(
            "UPDATE student_assignments SET payload = $1::jsonb, status = 'ready', completed_at = NOW() WHERE id = $2::uuid",
            json.dumps(cards), assignment_id,
        )


async def _generate_assignment_studyset(assignment_id: str, student_id: str, concept: dict, subject: str, source: str):
    async with get_db() as db:
        study_set = await db.fetchrow("""
            INSERT INTO study_sets (user_id, title, subject, description, status)
            VALUES ($1::uuid, $2, $3, $4, 'ready')
            RETURNING id
        """, student_id, f"Extra practice: {concept['title']}", subject, "Assigned by your teacher for extra practice")
        study_set_id = study_set["id"]

        # Auto-seed with the concept's source material so the student can chat
        # into it immediately — no PDF upload step needed.
        await db.execute("""
            INSERT INTO study_materials (study_set_id, filename, raw_text, char_count, status)
            VALUES ($1::uuid, $2, $3, $4, 'ready')
        """, study_set_id, f"{concept['title']}.txt", source, len(source))

        await db.execute(
            "UPDATE student_assignments SET study_set_id = $1::uuid, status = 'ready', completed_at = NOW() WHERE id = $2::uuid",
            study_set_id, assignment_id,
        )


async def _generate_assignment_video(assignment_id: str, concept: dict, subject: str, extra: str):
    from services.manim import (
        generate_solution_only, generate_manim_from_solution,
        fix_manim_colors, ensure_numpy_import, strip_invalid_tex_weight, _trigger_video_generation,
    )

    manim_subject = _map_manim_subject(subject)
    script        = concept["ai_transcript"] or concept["ai_summary"] or concept["title"]
    duration      = max(45, min(180, len(script) // 12))
    remedial_note = f"\n{extra}Keep it simpler and more remedial than a standard lesson — this student needs extra reinforcement.\n"
    prompt        = _build_concept_video_prompt(concept["title"], concept["source_text"], script, remedial_note)

    async with get_db() as db:
        video = await db.fetchrow("""
            INSERT INTO videos (prompt, subject, language, aspect_ratio, max_duration, status)
            VALUES ($1, $2, 'en', '16:9', $3, 'pending')
            RETURNING id
        """, prompt, manim_subject, duration)
        video_id = video["id"]
        await db.execute(
            "UPDATE student_assignments SET video_job_id = $1 WHERE id = $2::uuid", video_id, assignment_id,
        )

    solution_data = await generate_solution_only(prompt, "en", duration)
    async with get_db() as db:
        await db.execute("""
            UPDATE videos SET transcript_markdown = $1, verified_solution = $2,
                              status = 'transcript_ready', updated_at = NOW()
            WHERE id = $3
        """, solution_data["transcript_markdown"], solution_data["verified_solution"], video_id)

    code_data = await asyncio.wait_for(
        generate_manim_from_solution(solution_data, "en", duration, "16:9"), timeout=900
    )
    code     = fix_manim_colors(code_data["code"])
    code     = ensure_numpy_import(code)
    code     = strip_invalid_tex_weight(code)
    svg_urls = code_data.get("svg_urls") or {}

    async with get_db() as db:
        await db.execute("""
            UPDATE videos SET generated_code = $1, scene_name = $2, svg_urls = $3::jsonb,
                              status = 'queued', updated_at = NOW()
            WHERE id = $4
        """, code, code_data.get("scene_name", "MainScene"), json.dumps(svg_urls), video_id)

    logger.info("[assignment] %s: Manim code ready, triggering Cloud Run render (video %s)", assignment_id, video_id)
    _trigger_video_generation(video_id, svg_urls)
    # student_assignments.status stays 'generating' — GET /{id} lazily syncs from `videos`.
