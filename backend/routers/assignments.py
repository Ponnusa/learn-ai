"""
Differentiated, per-student assignments — quiz / flashcards / study set / video
targeted at one struggling student instead of the whole classroom. Reuses the
existing generation pipelines (courses.py's quiz/flashcard prompt builders, the
Manim concept-video pipeline) rather than duplicating them.

A generated quiz/flashcard set lands in 'pending_review' rather than going
straight to the student — a teacher must approve it first. Once approved and
taken, a quiz attempt's score/answers are recorded back onto the same row.

  POST   /api/assignments                     — teacher creates one (kicks off generation)
  GET    /api/assignments/student/{id}         — teacher: list a student's assignments
  GET    /api/assignments/mine                  — student: list my assignments (approved only)
  GET    /api/assignments/{id}                  — fetch one (lazily syncs video status)
  POST   /api/assignments/{id}/review           — teacher: approve a pending-review draft
  POST   /api/assignments/{id}/regenerate       — teacher: re-run generation on a pending-review draft
  DELETE /api/assignments/{id}                  — teacher: discard a pending-review or failed draft
  POST   /api/assignments/{id}/submit           — student: record a completed quiz's score/answers
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
from routers.students import _require_teacher_of_student, _summarize_ladder_report
from services.ai_router import openai_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assignments", tags=["assignments"])

_KINDS = ("quiz", "flashcards", "video", "studyset")
_TEACHER_TYPES = ("teacher", "institution_admin", "super_admin")


class CreateAssignmentRequest(BaseModel):
    student_id: str
    concept_id: str
    kind: str


async def _fetch_concept_and_ladder_report(teacher_id: str, concept_id: str, student_id: str) -> tuple[dict | None, dict | None]:
    """Look up a concept (scoped to this teacher) plus this student's own
    latest verified ladder session report for it, if one exists. Shared by
    create_assignment and regenerate_assignment so both feed generation the
    same personalization signal. Returns (None, None) if the concept isn't
    found or doesn't belong to this teacher."""
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.title, cc.ai_summary, cc.ai_transcript, cc.source_text,
                   c.subject, c.teacher_id
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
        if not concept or str(concept["teacher_id"]) != teacher_id:
            return None, None
        # This student's own latest verified ladder session on this concept,
        # if one resolved — the richest personalization signal we have,
        # used below to steer generation at the actual documented weak spot
        # instead of only the coarser struggle_areas/known_misconceptions.
        ladder_row = await db.fetchrow("""
            SELECT report FROM ladder_session_reports
            WHERE student_id = $1::uuid AND concept_id = $2::uuid AND status = 'ready'
            ORDER BY created_at DESC LIMIT 1
        """, student_id, concept_id)
    ladder_report = _summarize_ladder_report(ladder_row["report"]) if ladder_row else None
    return dict(concept), ladder_report


async def _require_teacher_owned_assignment(assignment_id: str, authorization: str) -> dict:
    """Teacher-only ownership check for the review/regenerate/discard actions
    below — reuses _get_user rather than _require_teacher_of_student since
    the assignment row's own teacher_id already proves the relationship,
    same style already used by get_assignment's ownership check."""
    caller_id, account_type = await _get_user(authorization)
    if account_type not in _TEACHER_TYPES:
        raise HTTPException(403, "Teacher only")
    async with get_db() as db:
        a = await db.fetchrow("SELECT * FROM student_assignments WHERE id = $1::uuid", assignment_id)
    if not a or str(a["teacher_id"]) != caller_id:
        raise HTTPException(404, "Assignment not found")
    return dict(a)


@router.post("")
async def create_assignment(
    req: CreateAssignmentRequest, bg: BackgroundTasks, authorization: str = Header(...)
):
    if req.kind not in _KINDS:
        raise HTTPException(400, f"kind must be one of {_KINDS}")

    teacher_id = await _require_teacher_of_student(authorization, req.student_id)
    concept, ladder_report = await _fetch_concept_and_ladder_report(teacher_id, req.concept_id, req.student_id)
    if not concept:
        raise HTTPException(404, "Concept not found")

    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO student_assignments (teacher_id, student_id, concept_id, kind, title, status)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, 'generating')
            RETURNING id
        """, teacher_id, req.student_id, req.concept_id, req.kind, concept["title"])
    assignment_id = str(row["id"])

    bg.add_task(_generate_assignment_bg, assignment_id, req.kind, concept, req.student_id, ladder_report)
    return {"id": assignment_id, "status": "generating"}


@router.get("/student/{student_id}")
async def list_assignments_for_student(student_id: str, authorization: str = Header(...)):
    await _require_teacher_of_student(authorization, student_id)
    return await _list_assignments(student_id)


@router.get("/mine")
async def list_my_assignments(authorization: str = Header(...)):
    student_id = await _get_student(authorization)
    return await _list_assignments(student_id, hide_unreviewed=True)


async def _list_assignments(student_id: str, hide_unreviewed: bool = False):
    query = """
        SELECT id, concept_id, kind, title, status, score, created_at
        FROM student_assignments WHERE student_id = $1::uuid
    """
    if hide_unreviewed:
        # A student must never see a draft still awaiting teacher approval.
        query += " AND status != 'pending_review'"
    query += " ORDER BY created_at DESC"
    async with get_db() as db:
        rows = await db.fetch(query, student_id)
    return [
        {
            "id":         str(r["id"]),
            "concept_id": str(r["concept_id"]) if r["concept_id"] else None,
            "kind":       r["kind"],
            "title":      r["title"],
            "status":     r["status"],
            "score":      r["score"],
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
    if not is_teacher and a["status"] == "pending_review":
        # Second layer on top of the list endpoint's filter — a student
        # should never see a draft awaiting approval, even by requesting
        # its id directly.
        raise HTTPException(404, "Assignment not found")

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
        "score":         a["score"],
        "answers":       a["answers"],
        "reviewed_at":   a["reviewed_at"].isoformat() if a["reviewed_at"] else None,
        "attempted_at":  a["attempted_at"].isoformat() if a["attempted_at"] else None,
    }


@router.post("/{assignment_id}/review")
async def approve_assignment(assignment_id: str, authorization: str = Header(...)):
    """Teacher approves a generated draft, making it visible to the student."""
    a = await _require_teacher_owned_assignment(assignment_id, authorization)
    if a["status"] != "pending_review":
        raise HTTPException(400, "Only a pending-review assignment can be approved")
    async with get_db() as db:
        await db.execute(
            "UPDATE student_assignments SET status = 'ready', reviewed_at = NOW() WHERE id = $1::uuid",
            assignment_id,
        )
    return {"status": "ready"}


@router.post("/{assignment_id}/regenerate")
async def regenerate_assignment(assignment_id: str, bg: BackgroundTasks, authorization: str = Header(...)):
    """Teacher discards a pending-review draft's content and re-runs
    generation in place, re-fetching the concept/ladder-report fresh in
    case anything changed since the original request."""
    a = await _require_teacher_owned_assignment(assignment_id, authorization)
    if a["status"] != "pending_review":
        raise HTTPException(400, "Can only regenerate a pending-review assignment")
    if not a["concept_id"]:
        raise HTTPException(400, "This assignment has no concept to regenerate from")

    concept, ladder_report = await _fetch_concept_and_ladder_report(
        str(a["teacher_id"]), str(a["concept_id"]), str(a["student_id"]),
    )
    if not concept:
        raise HTTPException(404, "Concept not found")

    async with get_db() as db:
        await db.execute(
            "UPDATE student_assignments SET status = 'generating', payload = NULL, error_message = NULL WHERE id = $1::uuid",
            assignment_id,
        )
    bg.add_task(_generate_assignment_bg, assignment_id, a["kind"], concept, str(a["student_id"]), ladder_report)
    return {"status": "generating"}


@router.delete("/{assignment_id}")
async def discard_assignment(assignment_id: str, authorization: str = Header(...)):
    """Teacher discards a draft that's either still awaiting review or
    failed to generate — the only two states with nothing worth keeping."""
    a = await _require_teacher_owned_assignment(assignment_id, authorization)
    if a["status"] not in ("pending_review", "failed"):
        raise HTTPException(400, "Can only discard a pending-review or failed assignment")
    async with get_db() as db:
        await db.execute("DELETE FROM student_assignments WHERE id = $1::uuid", assignment_id)
    return {"status": "deleted"}


class SubmitAssignmentRequest(BaseModel):
    score: float
    answers: list


@router.post("/{assignment_id}/submit")
async def submit_assignment(assignment_id: str, req: SubmitAssignmentRequest, authorization: str = Header(...)):
    """Student records their own completed quiz attempt — score plus the
    same per-question answer shape already used for regular concept quizzes
    ({qi, question, chosen, correct, ok}) — so a teacher can see completion
    and results from the Practice tab. This didn't exist before: assignment
    quizzes were graded entirely client-side and never reported back."""
    student_id = await _get_student(authorization)
    async with get_db() as db:
        a = await db.fetchrow(
            "SELECT student_id, kind, status, attempted_at FROM student_assignments WHERE id = $1::uuid", assignment_id
        )
    if not a or str(a["student_id"]) != student_id:
        raise HTTPException(404, "Assignment not found")
    if a["kind"] != "quiz":
        raise HTTPException(400, "Only quiz assignments can be submitted")
    if a["status"] != "ready":
        raise HTTPException(400, "Assignment is not ready")
    if a["attempted_at"] is not None:
        # One attempt per assigned quiz — enforced server-side, not just by
        # the UI locking answers in, so a student can't retake it by
        # replaying the request directly.
        raise HTTPException(400, "This quiz has already been submitted")

    async with get_db() as db:
        await db.execute("""
            UPDATE student_assignments
            SET score = $1, answers = $2::jsonb, attempted_at = NOW()
            WHERE id = $3::uuid
        """, req.score, json.dumps(req.answers), assignment_id)
    return {"status": "recorded"}


# ── Background generation ────────────────────────────────────────────────────

async def _generate_assignment_bg(assignment_id: str, kind: str, concept: dict, student_id: str, ladder_report: dict | None = None):
    try:
        async with get_db() as db:
            profile = await db.fetchrow(
                "SELECT struggle_areas, known_misconceptions FROM student_profiles WHERE user_id = $1::uuid",
                student_id,
            )
            student_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", student_id)
        weak_spots = [*(profile["struggle_areas"] or []), *(profile["known_misconceptions"] or [])] if profile else []
        extra = (
            f"This student is struggling with: {', '.join(weak_spots[:5])}. "
            "Emphasize and reinforce these specific weak areas.\n"
            if weak_spots else ""
        )
        # A resolved+verified guided-discovery session on this exact concept
        # is the richest signal we have — but it cuts two different ways.
        # A report only exists once a chain has been verified, i.e. this
        # concept is already mastered, so if the report also offered a
        # concrete stretch idea (optional_extension — the same text shown
        # to the teacher as "Ready for more"), this should be enrichment,
        # not more remediation on something already mastered. Only fall
        # back to targeting the weakest dimension when there's no stretch
        # idea to build on — mirrors the same precedence the Practice tab
        # UI uses to decide between its "Ready for more" and "Focus" lines.
        if ladder_report and ladder_report.get("optional_extension"):
            extra += (
                f"This student has already mastered this concept (they resolved a verified guided-discovery "
                f"session on it). They're ready for enrichment, not remediation. Their tutor session suggested "
                f"this stretch direction: {ladder_report['optional_extension']}\n"
                "Design this content as an enrichment/extension challenge building on that idea — go deeper, "
                "broader, or harder than a standard review of this concept, not basic reinforcement of what "
                "they already showed they understand.\n"
            )
        elif ladder_report and ladder_report.get("weak_dimension"):
            extra += (
                f"This student's guided-discovery session on this concept showed their weakest area is "
                f"{ladder_report['weak_dimension']} ({ladder_report.get('weak_level') or 'Developing'}). "
                f"Specific growth step identified: {ladder_report.get('next_growth_step') or 'apply the idea to a new situation'}\n"
                "Design this content to directly exercise that gap — e.g. if the gap is applying the idea "
                "to new situations or recognizing what changes an outcome, include at least one question/card "
                "that requires exactly that, not just recall of what was already covered.\n"
            )

        source   = concept["source_text"] or concept["ai_summary"] or concept["title"]
        subject  = concept["subject"] or "General"
        language = student_lang or 'en'

        if kind == "quiz":
            await _generate_assignment_quiz(assignment_id, concept["title"], subject, source, extra, language)
        elif kind == "flashcards":
            await _generate_assignment_flashcards(assignment_id, concept["title"], source, extra, language)
        elif kind == "studyset":
            await _generate_assignment_studyset(assignment_id, student_id, concept, subject, source)
        elif kind == "video":
            await _generate_assignment_video(assignment_id, concept, subject, extra, language, user_id=student_id)

    except Exception as exc:
        logger.error("[assignment] %s (%s) failed: %s", assignment_id, kind, exc, exc_info=True)
        async with get_db() as db:
            await db.execute(
                "UPDATE student_assignments SET status = 'failed', error_message = $1 WHERE id = $2::uuid",
                str(exc)[:2000], assignment_id,
            )


async def _generate_assignment_quiz(assignment_id: str, title: str, subject: str, source: str, extra: str, language: str = 'en'):
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": build_quiz_prompt(title, subject, source, extra, language=language)}],
        response_format={"type": "json_object"},
        max_tokens=3000,
        temperature=0.3,
    )
    questions = json.loads(response.choices[0].message.content).get("questions", [])

    async with get_db() as db:
        await db.execute(
            "UPDATE student_assignments SET payload = $1::jsonb, status = 'pending_review', completed_at = NOW() WHERE id = $2::uuid",
            json.dumps(questions), assignment_id,
        )


async def _generate_assignment_flashcards(assignment_id: str, title: str, source: str, extra: str, language: str = 'en'):
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": build_flashcard_prompt(title, source, extra, language=language)}],
        response_format={"type": "json_object"},
        max_tokens=2500,
        temperature=0.3,
    )
    cards = json.loads(response.choices[0].message.content).get("flashcards", [])

    async with get_db() as db:
        await db.execute(
            "UPDATE student_assignments SET payload = $1::jsonb, status = 'pending_review', completed_at = NOW() WHERE id = $2::uuid",
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


async def _generate_assignment_video(assignment_id: str, concept: dict, subject: str, extra: str, language: str = 'en', user_id: str | None = None):
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
            VALUES ($1, $2, $4, '16:9', $3, 'pending')
            RETURNING id
        """, prompt, manim_subject, duration, language)
        video_id = video["id"]
        await db.execute(
            "UPDATE student_assignments SET video_job_id = $1 WHERE id = $2::uuid", video_id, assignment_id,
        )

    solution_data = await generate_solution_only(prompt, language, duration)
    async with get_db() as db:
        await db.execute("""
            UPDATE videos SET transcript_markdown = $1, verified_solution = $2,
                              status = 'transcript_ready', updated_at = NOW()
            WHERE id = $3
        """, solution_data["transcript_markdown"], solution_data["verified_solution"], video_id)

    # ── Storyboard branch (multimodal_video_enabled) ─────────────────────────
    _multimodal = False
    if user_id:
        async with get_db() as db:
            _multimodal = await db.fetchval(
                "SELECT multimodal_video_enabled FROM users WHERE id = $1::uuid", user_id
            )
    if _multimodal:
        logger.info("[assignment] %s: multimodal enabled -> storyboard path (video %s)", assignment_id, video_id)
        from worker_pipeline.storyboard import generate_storyboard
        storyboard = await asyncio.to_thread(
            generate_storyboard,
            lesson_id=str(video_id),
            topic=prompt,
            verified_solution=solution_data["verified_solution"],
            subject_area=manim_subject or "general",
            target_duration_seconds=duration,
            enable_veo=False,
            aspect_ratio="16:9",
        )
        async with get_db() as db:
            await db.executemany("""
                INSERT INTO video_segments
                  (video_id, segment_id, segment_order, type,
                   target_duration_seconds, subject_area, aspect_ratio,
                   narration_text, generation_prompt,
                   style_reference_segment_id, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'pending')
            """, [
                (video_id, s.id, s.order, s.type,
                 s.target_duration_seconds, s.subject_area, s.aspect_ratio,
                 s.narration_text, s.generation_prompt, s.style_reference_segment_id)
                for s in storyboard.segments
            ])
            await db.execute(
                "UPDATE videos SET status='queued', updated_at=NOW() WHERE id=$1", video_id,
            )
        _trigger_video_generation(video_id, {})
        return

    code_data = await asyncio.wait_for(
        generate_manim_from_solution(solution_data, language, duration, "16:9"), timeout=900
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
