"""
Course builder router — teachers create courses (units + concepts),
optionally imported from a syllabus PDF, then assign to classrooms.
"""
import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header, Request, UploadFile, File, Form
from fastapi.responses import Response, RedirectResponse
from pydantic import BaseModel

from database import get_db
from routers.auth import decode_jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/courses", tags=["courses"])

_LANGUAGE_NAMES = {'fi': 'Finnish', 'sv': 'Swedish', 'es': 'Spanish', 'fr': 'French'}


async def _summarize_one_concept(concept_id: str, course: dict | None):
    """Generate AI summary + transcript for a single concept ('Generate explanation')."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    try:
        async with get_db() as db:
            concept = await db.fetchrow(
                "SELECT title, description, source_text FROM course_concepts WHERE id = $1::uuid",
                concept_id,
            )
            # Look up the teacher's language through the concept → unit → course → teacher chain
            lang_val = await db.fetchval("""
                SELECT u.language
                FROM course_concepts cc
                JOIN course_units cu ON cu.id = cc.unit_id
                JOIN courses c       ON c.id  = cu.course_id
                JOIN users u         ON u.id  = c.teacher_id
                WHERE cc.id = $1::uuid
            """, concept_id)
        if not concept:
            return

        language = lang_val or 'en'
        source = concept["source_text"] or concept["description"] or concept["title"]
        subject = (course["subject"] if course else None) or "General"
        grade   = (course.get("grade") if course else None) or ""
        board   = (course.get("board") if course else None) or ""

        lang_instruction = ""
        if language in _LANGUAGE_NAMES:
            lang_name = _LANGUAGE_NAMES[language]
            lang_instruction = f'\n\nIMPORTANT: Write ALL content in {lang_name}. Do not use English.'

        grade_line = f"\nGrade: {grade}" if grade else ""
        board_line = f"\nCurriculum Board: {board}" if board else ""
        prompt = f"""You are an expert educator creating study material for students.

Concept: {concept['title']}
Subject: {subject}{grade_line}{board_line}

Source material (from the chapter):
---
{source}
---

STEP 1 — Classify the source:
A) WORKED EXAMPLE / CALCULATION — source contains formulas, numbered steps, given values, a solution procedure, or a numerical answer.
B) CONCEPTUAL — source explains ideas, definitions, or principles without a specific problem to solve.

STEP 2 — Create a SUMMARY and TRANSCRIPT based on the type:

If type A (worked example / calculation):
  SUMMARY — use this exact structure, each section on its own line:
  [One sentence stating what the problem asks for]

  Tunnetut suureet / Given:
  [Each known value on its own line, exactly as written in source, e.g. "NA = 6,022 · 10²³ kpl/mol"]

  Kaava / Formula:
  [The relevant formula(s), e.g. "N = n · NA"]

  Ratkaisu / Solution:
  [Full substitution with real numbers from the source, e.g. "N = 667 mol · 6,022 · 10²³ kpl/mol"]
  [Show the unrounded intermediate result on its own line, e.g. "= 4,0167 · 10²⁶ kpl"]
  [Then the rounded result, e.g. "≈ 4,02 · 10²⁶ kpl"]

  Vastaus / Answer:
  [Final answer with symbol, value, and unit, e.g. "N(N₂) = 4,02 · 10²⁶ kpl"]

  Rules: copy every number exactly from the source — do NOT round early, do NOT skip the intermediate result, do NOT paraphrase the values.
  Preserve all domain-specific notation verbatim: reaction arrows (→ ⇌), state symbols (aq) (s) (l) (g), unit symbols (mol, J, N, m³, kpl/mol), and mathematical operators exactly as they appear in the source.
  Math formatting: use $...$ for inline math (e.g. $N_A = 6{{,}}022 \\times 10^{{23}}$) and $$...$$ for display equations (e.g. $$N = n \\times N_A$$). Never use \\[...\\] or bare brackets.

  TRANSCRIPT (teacher talking through the solution step by step):
  - Open: "In this example we want to find..."
  - Read out each given value: "We know that n equals 667 mol, and Avogadro's number is..."
  - Say the formula, then the substitution with real numbers
  - Say the intermediate result, then the rounded answer
  - End: "So the answer is..."

If type B (conceptual):
  SUMMARY:
  - Plain-language definition first
  - Explain key ideas with examples from the source
  - 3–4 paragraphs, accurate to the source, do not invent examples not present

  TRANSCRIPT:
  - Conversational spoken-word style
  - Open with "In this lesson, we'll explore [concept]..."
  - Mirror the summary but as natural speech
  - End with a brief recap

Return ONLY valid JSON:
{{"summary": "...", "transcript": "..."}}{lang_instruction}"""

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=3000,
            temperature=0.2,
        )
        result = json.loads(response.choices[0].message.content)

        async with get_db() as db:
            await db.execute("""
                UPDATE course_concepts
                SET ai_summary = $1, ai_transcript = $2, pipeline_status = 'ready'
                WHERE id = $3::uuid
            """, result.get("summary", ""), result.get("transcript", ""), concept_id)

    except Exception as exc:
        logger.error("[pipeline] concept %s failed: %s", concept_id, exc)
        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET pipeline_status = 'failed' WHERE id = $1::uuid",
                concept_id,
            )


async def _generate_suggested_prompts_bg(concept_id: str) -> None:
    """
    Background: generate 5-6 teaching prompt suggestions for the teacher studio chat.
    Uses GPT-4o-mini and stores results in suggested_prompts JSONB on the concept.
    Called automatically after summarisation and via the manual endpoint.
    Silently skips if no source_text is available.
    """
    from openai import AsyncOpenAI
    try:
        async with get_db() as db:
            row = await db.fetchrow("""
                SELECT cc.title, cc.source_text, c.subject
                FROM course_concepts cc
                JOIN course_units cu ON cu.id = cc.unit_id
                JOIN courses c       ON c.id  = cu.course_id
                WHERE cc.id = $1::uuid
            """, concept_id)
        if not row or not row["source_text"]:
            return

        title   = row["title"]
        subject = row["subject"] or "General"
        source  = (row["source_text"] or "")[:1500]

        client = AsyncOpenAI()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": (
                    "You generate ready-to-use teacher prompt suggestions for an AI teacher studio chat. "
                    "The teacher can click one to instantly send it to the AI. "
                    "Generate exactly 6 prompts covering different teaching needs. "
                    "Each prompt should be a complete question or instruction the teacher sends to the AI, "
                    "10-20 words, specific to this concept. "
                    "Cover these angles: (1) class discussion questions, (2) student misconceptions, "
                    "(3) formative check questions, (4) hands-on activity or lab idea, "
                    "(5) real-world connection or analogy, (6) vocabulary/key terms emphasis. "
                    "Return ONLY a JSON array of 6 strings, no explanations."
                ),
            }, {
                "role": "user",
                "content": f"Concept: {title}\nSubject: {subject}\n\nSource excerpt:\n{source}",
            }],
            response_format={"type": "json_object"},
            max_tokens=400,
            temperature=0.4,
        )
        data = json.loads(resp.choices[0].message.content)
        # Accept array at top level or under any key
        if isinstance(data, list):
            prompts = data
        else:
            prompts = next((v for v in data.values() if isinstance(v, list)), [])

        prompts = [str(p).strip() for p in prompts if str(p).strip()][:6]
        if not prompts:
            return

        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET suggested_prompts = $1::jsonb WHERE id = $2::uuid",
                json.dumps(prompts), concept_id,
            )
    except Exception as exc:
        logger.warning("[prompts] concept %s suggestion generation failed: %s", concept_id, exc)


async def _summarize_concepts_bg(concept_ids: list[str], course_id: str):
    """Background: generate AI summary + transcript per concept, one at a time."""
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT name, subject, grade, board FROM courses WHERE id = $1::uuid", course_id
        )
    for concept_id in concept_ids:
        await _summarize_one_concept(concept_id, dict(course) if course else None)
        # Generate teaching prompt suggestions after summarisation (fire-and-forget)
        try:
            await _generate_suggested_prompts_bg(concept_id)
        except Exception:
            pass  # never fail the pipeline over suggestion generation


async def _require_teacher(authorization: str):
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT id, account_type, is_active FROM users WHERE id = $1::uuid", user_id
        )
    if not row or not row["is_active"]:
        raise HTTPException(403, "Account inactive")
    if row["account_type"] not in ("teacher", "institution_admin", "super_admin"):
        raise HTTPException(403, "Teacher access required")
    return str(row["id"])


# ── Course CRUD ───────────────────────────────────────────────────────────────

class CreateCourseRequest(BaseModel):
    name:        str
    description: str | None = None
    subject:     str | None = None
    grade:       str | None = None
    board:       str | None = None


@router.post("")
async def create_course(req: CreateCourseRequest, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO courses (teacher_id, name, description, subject, grade, board)
            VALUES ($1::uuid, $2, $3, $4, $5, $6)
            RETURNING id, name, description, subject, grade, board, status, created_at
        """, teacher_id, req.name, req.description, req.subject, req.grade, req.board)
    return _fmt_course(row)


@router.get("/mine")
async def list_my_courses(authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT c.id, c.name, c.description, c.subject, c.grade, c.board, c.status, c.created_at,
                   COUNT(DISTINCT cu.id) AS unit_count,
                   COUNT(DISTINCT cc.id) AS concept_count,
                   COUNT(DISTINCT cc.id) FILTER (
                       WHERE cc.quiz_status = 'failed' OR cc.flashcard_status = 'failed'
                          OR cc.audio_status = 'failed' OR cc.video_status = 'failed'
                   ) AS failed_count
            FROM courses c
            LEFT JOIN course_units    cu ON cu.course_id = c.id
            LEFT JOIN course_concepts cc ON cc.unit_id   = cu.id
            WHERE c.teacher_id = $1::uuid
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """, teacher_id)
    return [
        {
            **_fmt_course(r),
            "unit_count":    int(r["unit_count"] or 0),
            "concept_count": int(r["concept_count"] or 0),
            "failed_count":  int(r["failed_count"] or 0),
        }
        for r in rows
    ]


@router.get("/progress-overview")
async def get_progress_overview(authorization: str = Header(...)):
    """
    Teacher-only summary across all of a teacher's courses: enrolled student
    count, average % of concepts visited, average quiz score, and failed-asset
    count — used as the landing view for "Student Progress" before drilling
    into a specific course's full grid (GET /{course_id}/progress).
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        courses = await db.fetch("""
            SELECT c.id, c.name, c.status, c.created_at,
                   COUNT(DISTINCT cc.id) AS concept_count,
                   COUNT(DISTINCT cc.id) FILTER (
                       WHERE cc.quiz_status = 'failed' OR cc.flashcard_status = 'failed'
                          OR cc.audio_status = 'failed' OR cc.video_status = 'failed'
                   ) AS failed_count
            FROM courses c
            LEFT JOIN course_units    cu ON cu.course_id = c.id
            LEFT JOIN course_concepts cc ON cc.unit_id   = cu.id
            WHERE c.teacher_id = $1::uuid
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """, teacher_id)

        student_counts = await db.fetch("""
            SELECT clc.course_id, COUNT(DISTINCT cs.student_id) AS student_count
            FROM classroom_courses clc
            JOIN classrooms cl         ON cl.id = clc.classroom_id AND cl.teacher_id = $1::uuid
            JOIN classroom_students cs ON cs.classroom_id = cl.id
            GROUP BY clc.course_id
        """, teacher_id)

        progress = await db.fetch("""
            SELECT cu.course_id,
                   COUNT(*) FILTER (WHERE scp.visited) AS visited_rows,
                   AVG(scp.quiz_score) AS avg_quiz_score
            FROM student_concept_progress scp
            JOIN course_concepts cc ON cc.id = scp.concept_id
            JOIN course_units cu    ON cu.id = cc.unit_id
            JOIN courses c          ON c.id = cu.course_id AND c.teacher_id = $1::uuid
            GROUP BY cu.course_id
        """, teacher_id)

    student_count_map = {str(r["course_id"]): int(r["student_count"]) for r in student_counts}
    progress_map = {str(r["course_id"]): r for r in progress}

    result = []
    for c in courses:
        cid           = str(c["id"])
        student_count = student_count_map.get(cid, 0)
        concept_count = int(c["concept_count"] or 0)
        prog          = progress_map.get(cid)
        possible      = student_count * concept_count
        visited_pct   = (
            round(100 * int(prog["visited_rows"]) / possible) if prog and possible > 0 else None
        )
        avg_quiz_score = round(prog["avg_quiz_score"]) if prog and prog["avg_quiz_score"] is not None else None

        result.append({
            "id":             cid,
            "name":           c["name"],
            "status":         c["status"],
            "student_count":  student_count,
            "concept_count":  concept_count,
            "failed_count":   int(c["failed_count"] or 0),
            "visited_pct":    visited_pct,
            "avg_quiz_score": avg_quiz_score,
        })
    return result


def _compute_risk(avg_quiz_score, visited_pct, concept_count, last_seen_at) -> str:
    """Deterministic risk flag — no AI call, just thresholds on existing progress data."""
    now = datetime.now(tz=timezone.utc)
    days_inactive = (now - last_seen_at).days if last_seen_at else None

    at_risk = (
        (avg_quiz_score is not None and avg_quiz_score < 40)
        or (days_inactive is not None and days_inactive >= 7)
        or (concept_count > 0 and visited_pct is not None and visited_pct < 30)
    )
    if at_risk:
        return "at_risk"
    watch = (
        (avg_quiz_score is not None and avg_quiz_score < 60)
        or (days_inactive is not None and days_inactive >= 3)
    )
    return "watch" if watch else "ok"


@router.get("/students-overview")
async def get_students_overview(authorization: str = Header(...)):
    """
    Teacher-only roster across ALL of a teacher's classrooms (student-first,
    as opposed to /progress-overview's course-first view): per student,
    classrooms, % concepts visited, avg quiz score, due flashcards, last
    active, and a deterministic risk flag for spotting struggling students.
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        roster = await db.fetch("""
            SELECT cs.student_id, u.name, u.email, u.last_seen_at,
                   cl.id AS classroom_id, cl.name AS classroom_name
            FROM classroom_students cs
            JOIN classrooms cl ON cl.id = cs.classroom_id AND cl.teacher_id = $1::uuid
            JOIN users u       ON u.id = cs.student_id
        """, teacher_id)

        concept_counts = await db.fetch("""
            SELECT cs.student_id, COUNT(DISTINCT cc.id) AS concept_count
            FROM classroom_students cs
            JOIN classrooms cl         ON cl.id = cs.classroom_id AND cl.teacher_id = $1::uuid
            JOIN classroom_courses clc ON clc.classroom_id = cl.id
            JOIN course_units cu       ON cu.course_id = clc.course_id
            JOIN course_concepts cc    ON cc.unit_id = cu.id
            GROUP BY cs.student_id
        """, teacher_id)

        progress = await db.fetch("""
            SELECT scp.student_id,
                   COUNT(DISTINCT scp.concept_id) FILTER (WHERE scp.visited) AS visited_count,
                   AVG(scp.quiz_score) AS avg_quiz_score
            FROM student_concept_progress scp
            JOIN course_concepts cc ON cc.id = scp.concept_id
            JOIN course_units cu    ON cu.id = cc.unit_id
            JOIN courses c          ON c.id = cu.course_id AND c.teacher_id = $1::uuid
            GROUP BY scp.student_id
        """, teacher_id)

        due_flashcards = await db.fetch("""
            SELECT cs.student_id,
                   COUNT(DISTINCT cf.id) FILTER (
                       WHERE cfs.due_at IS NULL OR cfs.due_at <= NOW()
                   ) AS due_count
            FROM classroom_students cs
            JOIN classrooms cl         ON cl.id = cs.classroom_id AND cl.teacher_id = $1::uuid
            JOIN classroom_courses clc ON clc.classroom_id = cl.id
            JOIN course_units cu       ON cu.course_id = clc.course_id
            JOIN course_concepts cc    ON cc.unit_id = cu.id AND cc.flashcard_status = 'approved'
            JOIN concept_flashcards cf ON cf.concept_id = cc.id
            LEFT JOIN concept_flashcard_state cfs
                   ON cfs.flashcard_id = cf.id AND cfs.student_id = cs.student_id
            GROUP BY cs.student_id
        """, teacher_id)

    concept_count_map = {str(r["student_id"]): int(r["concept_count"] or 0) for r in concept_counts}
    progress_map      = {str(r["student_id"]): r for r in progress}
    due_map           = {str(r["student_id"]): int(r["due_count"] or 0) for r in due_flashcards}

    students: dict[str, dict] = {}
    for r in roster:
        sid = str(r["student_id"])
        if sid not in students:
            students[sid] = {
                "id": sid, "name": r["name"], "email": r["email"],
                "last_seen_at": r["last_seen_at"], "classrooms": [],
            }
        students[sid]["classrooms"].append({"id": str(r["classroom_id"]), "name": r["classroom_name"]})

    result = []
    for sid, s in students.items():
        concept_count = concept_count_map.get(sid, 0)
        prog          = progress_map.get(sid)
        visited_pct   = (
            round(100 * int(prog["visited_count"]) / concept_count)
            if prog and concept_count > 0 else None
        )
        avg_quiz_score = round(prog["avg_quiz_score"]) if prog and prog["avg_quiz_score"] is not None else None
        last_seen_at   = s["last_seen_at"]

        result.append({
            "id":             sid,
            "name":           s["name"],
            "email":          s["email"],
            "classrooms":     s["classrooms"],
            "concept_count":  concept_count,
            "visited_pct":    visited_pct,
            "avg_quiz_score": avg_quiz_score,
            "due_flashcards": due_map.get(sid, 0),
            "last_seen_at":   last_seen_at.isoformat() if last_seen_at else None,
            "risk":           _compute_risk(avg_quiz_score, visited_pct, concept_count, last_seen_at),
        })

    result.sort(key=lambda s: (s["risk"] != "at_risk", s["risk"] != "watch", s["name"] or ""))
    return result


@router.get("/all-curriculum-contexts")
async def list_curriculum_contexts_top(authorization: str = Header(...)):
    """
    Returns all available curriculum contexts for the teacher dropdown.
    Declared before /{course_id} so FastAPI matches it correctly.
    """
    await _require_teacher(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, name, driving_question, grade_level, subject,
                   active_lesson, lesson_count, teks_codes
            FROM curriculum_contexts
            ORDER BY grade_level, name
        """)
    return [
        {
            "id":               str(r["id"]),
            "name":             r["name"],
            "driving_question": r["driving_question"],
            "grade_level":      r["grade_level"],
            "subject":          r["subject"],
            "active_lesson":    r["active_lesson"],
            "lesson_count":     r["lesson_count"],
            "teks_codes":       r["teks_codes"] or [],
        }
        for r in rows
    ]


@router.get("/standards/search")
async def search_standards(
    q:       str  = "",
    grade:   str  = "",
    subject: str  = "Science",
    board:   str  = "TEKS",
    limit:   int  = 20,
    authorization: str = Header(...),
):
    """Search seeded curriculum standards. Returns sub-standards only (has a letter suffix)."""
    await _require_teacher(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT short_code, case_code, grade, title
            FROM standards
            WHERE board = $1
              AND ($2 = '' OR grade = $2)
              AND short_code ~ '[A-Z]$'
              AND ($3 = '' OR title ILIKE '%' || $3 || '%' OR short_code ILIKE $3 || '%')
            ORDER BY grade, sort_order
            LIMIT $4
        """, board, grade, q.strip(), limit)
    return [
        {"code": r["short_code"], "case_code": r["case_code"], "grade": r["grade"], "title": r["title"]}
        for r in rows
    ]


class CreateCurriculumContextRequest(BaseModel):
    name:             str
    grade_level:      str
    subject:          str       = "Science"
    board:            str       = "TEKS"
    teks_codes:       list[str] = []
    driving_question: str | None = None
    lesson_count:     int        = 1


@router.post("/curriculum-contexts")
async def create_curriculum_context(req: CreateCurriculumContextRequest, authorization: str = Header(...)):
    """Teacher creates a lightweight curriculum context by picking standards codes."""
    await _require_teacher(authorization)
    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO curriculum_contexts
                (name, grade_level, subject, teks_codes, driving_question, lesson_count, active_lesson)
            VALUES ($1, $2, $3, $4, $5, $6, 1)
            RETURNING id, name, grade_level, subject, teks_codes, driving_question, lesson_count, active_lesson
        """, req.name, req.grade_level, req.subject,
             req.teks_codes or [], req.driving_question, req.lesson_count)
    return {
        "id":               str(row["id"]),
        "name":             row["name"],
        "grade_level":      row["grade_level"],
        "subject":          row["subject"],
        "teks_codes":       row["teks_codes"] or [],
        "driving_question": row["driving_question"],
        "lesson_count":     row["lesson_count"],
        "active_lesson":    row["active_lesson"],
    }


@router.get("/{course_id}")
async def get_course(course_id: str, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT * FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        if not course:
            raise HTTPException(404, "Course not found")

        units = await db.fetch("""
            SELECT id, title, description, position, chapter_ref FROM course_units
            WHERE course_id = $1::uuid ORDER BY position, created_at
        """, course_id)

        unit_ids = [str(u["id"]) for u in units]
        concepts = []
        if unit_ids:
            concepts = await db.fetch("""
                SELECT cc.id, cc.unit_id, cc.title, cc.description,
                       cc.study_set_id, cc.position, cc.pipeline_status, cc.source,
                       cc.quiz_status, cc.flashcard_status, cc.audio_status, cc.video_status,
                       ss.status AS ss_status,
                       COALESCE(chat.msg_count, 0) AS chat_msg_count,
                       chat.last_msg_at               AS last_activity_at,
                       COALESCE(blocks.block_count, 0) AS textbook_block_count
                FROM course_concepts cc
                LEFT JOIN study_sets ss ON ss.id = cc.study_set_id
                LEFT JOIN (
                    SELECT conv.concept_id,
                           COUNT(m.id)       AS msg_count,
                           MAX(m.created_at) AS last_msg_at
                    FROM conversations conv
                    LEFT JOIN messages m ON m.conversation_id = conv.id
                    WHERE conv.concept_id IS NOT NULL
                    GROUP BY conv.concept_id
                ) chat ON chat.concept_id = cc.id
                LEFT JOIN (
                    SELECT concept_id, COUNT(*) AS block_count
                    FROM concept_content_blocks
                    GROUP BY concept_id
                ) blocks ON blocks.concept_id = cc.id
                WHERE cc.unit_id = ANY($1::uuid[])
                ORDER BY cc.unit_id, cc.position, cc.created_at
            """, unit_ids)

        # Assigned classrooms
        classrooms = await db.fetch("""
            SELECT cl.id, cl.name FROM classroom_courses cc
            JOIN classrooms cl ON cl.id = cc.classroom_id
            WHERE cc.course_id = $1::uuid
        """, course_id)

    # Group concepts by unit
    concept_map: dict[str, list] = {uid: [] for uid in unit_ids}
    for c in concepts:
        uid = str(c["unit_id"])
        if uid in concept_map:
            concept_map[uid].append({
                "id":                   str(c["id"]),
                "title":                c["title"],
                "description":          c["description"],
                "study_set_id":         str(c["study_set_id"]) if c["study_set_id"] else None,
                "ss_status":            c["ss_status"],
                "position":             c["position"],
                "pipeline_status":      c["pipeline_status"],
                "source":               c["source"],
                "quiz_status":          c["quiz_status"],
                "flashcard_status":     c["flashcard_status"],
                "audio_status":         c["audio_status"],
                "video_status":         c["video_status"],
                "chat_msg_count":       int(c["chat_msg_count"] or 0),
                "last_activity_at":     c["last_activity_at"].isoformat() if c["last_activity_at"] else None,
                "textbook_block_count": int(c["textbook_block_count"] or 0),
            })

    return {
        **_fmt_course(course),
        "units": [
            {
                "id":          str(u["id"]),
                "title":       u["title"],
                "description": u["description"],
                "position":    u["position"],
                "chapter_ref": str(u["chapter_ref"]) if u["chapter_ref"] else None,
                "concepts":    concept_map.get(str(u["id"]), []),
            }
            for u in units
        ],
        "classrooms": [{"id": str(cl["id"]), "name": cl["name"]} for cl in classrooms],
    }


@router.get("/{course_id}/progress")
async def get_course_progress(course_id: str, authorization: str = Header(...)):
    """
    Teacher-only grid: every student enrolled (via any classroom this course is
    assigned to) x every concept in the course, with visited/quiz_score cells.
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id, name FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        if not course:
            raise HTTPException(404, "Course not found")

        concepts = await db.fetch("""
            SELECT cc.id, cc.title, cu.title AS unit_title, cu.position AS unit_position, cc.position
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid
            ORDER BY cu.position, cu.created_at, cc.position, cc.created_at
        """, course_id)

        students = await db.fetch("""
            SELECT DISTINCT u.id, u.name, u.email
            FROM classroom_courses clc
            JOIN classrooms cl            ON cl.id = clc.classroom_id
            JOIN classroom_students cs    ON cs.classroom_id = cl.id
            JOIN users u                  ON u.id = cs.student_id
            WHERE clc.course_id = $1::uuid AND cl.teacher_id = $2::uuid
            ORDER BY u.name
        """, course_id, teacher_id)

        progress = await db.fetch("""
            SELECT scp.student_id, scp.concept_id, scp.visited, scp.quiz_score,
                   scp.last_seen_at
            FROM student_concept_progress scp
            JOIN course_concepts cc ON cc.id = scp.concept_id
            JOIN course_units cu    ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid
        """, course_id)

        # Quiz attempt history per (student, concept) — up to 5 most recent
        attempt_rows = await db.fetch("""
            SELECT qa.student_id, qa.concept_id, qa.score
            FROM concept_quiz_attempts qa
            JOIN course_concepts cc ON cc.id = qa.concept_id
            JOIN course_units cu    ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid
            ORDER BY qa.student_id, qa.concept_id, qa.taken_at ASC
        """, course_id)

        # Total video content blocks per concept (≠ legacy single-video)
        video_block_total_rows = await db.fetch("""
            SELECT ccb.concept_id, COUNT(*) AS total
            FROM concept_content_blocks ccb
            JOIN course_concepts cc ON cc.id = ccb.concept_id
            JOIN course_units cu    ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid AND ccb.type = 'video' AND ccb.in_textbook = true
            GROUP BY ccb.concept_id
        """, course_id)

        # How many of those blocks each student has watched ≥ 75 %
        video_watched_rows = await db.fetch("""
            SELECT vw.student_id, vw.concept_id, COUNT(*) AS watched
            FROM concept_video_watches vw
            JOIN course_concepts cc ON cc.id = vw.concept_id
            JOIN course_units cu    ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid
              AND vw.pct_watched >= 75
              AND vw.block_id != 'legacy'
            GROUP BY vw.student_id, vw.concept_id
        """, course_id)

        # Flashcard mastery: latest review rating per (student, flashcard) → % mastered (≥3)
        flashcard_rows = await db.fetch("""
            WITH total_cards AS (
                SELECT cf.concept_id, COUNT(*) AS total
                FROM concept_flashcards cf
                JOIN course_concepts cc ON cc.id = cf.concept_id
                JOIN course_units cu    ON cu.id = cc.unit_id
                WHERE cu.course_id = $1::uuid
                GROUP BY cf.concept_id
            ),
            latest AS (
                SELECT DISTINCT ON (cfr.student_id, cfr.flashcard_id)
                       cfr.student_id, cf.concept_id, cfr.rating
                FROM concept_flashcard_reviews cfr
                JOIN concept_flashcards cf ON cf.id = cfr.flashcard_id
                JOIN course_concepts cc ON cc.id = cf.concept_id
                JOIN course_units cu    ON cu.id = cc.unit_id
                WHERE cu.course_id = $1::uuid
                ORDER BY cfr.student_id, cfr.flashcard_id, cfr.reviewed_at DESC
            )
            SELECT lr.student_id, lr.concept_id,
                   tc.total                                          AS total_cards,
                   COUNT(*) FILTER (WHERE lr.rating >= 3)           AS mastered_cards
            FROM latest lr
            JOIN total_cards tc ON tc.concept_id = lr.concept_id
            GROUP BY lr.student_id, lr.concept_id, tc.total
        """, course_id)

    video_total_map: dict[str, int] = {str(r["concept_id"]): int(r["total"]) for r in video_block_total_rows}
    video_watched_map: dict[tuple, int] = {
        (str(r["student_id"]), str(r["concept_id"])): int(r["watched"]) for r in video_watched_rows
    }

    attempt_map_grid: dict[tuple, list] = {}
    for r in attempt_rows:
        key = (str(r["student_id"]), str(r["concept_id"]))
        attempt_map_grid.setdefault(key, []).append(round(r["score"]))
    for key in attempt_map_grid:
        attempt_map_grid[key] = attempt_map_grid[key][-5:]

    flashcard_map: dict[tuple, dict] = {}
    for r in flashcard_rows:
        total    = int(r["total_cards"]   or 0)
        mastered = int(r["mastered_cards"] or 0)
        flashcard_map[(str(r["student_id"]), str(r["concept_id"]))] = {
            "flashcard_pct":      round(mastered / total * 100) if total > 0 else None,
            "flashcard_mastered": mastered,
            "flashcard_total":    total,
        }

    progress_map: dict[tuple, dict] = {
        (str(p["student_id"]), str(p["concept_id"])): {
            "visited":      p["visited"],
            "quiz_score":   p["quiz_score"],
            "last_seen_at": p["last_seen_at"],
        }
        for p in progress
    }

    concept_list = [
        {"id": str(c["id"]), "title": c["title"], "unit_title": c["unit_title"]}
        for c in concepts
    ]

    student_rows = []
    for s in students:
        sid = str(s["id"])
        cells: dict = {}
        visited_count = 0
        scores: list = []
        last_seen_at  = None
        for c in concept_list:
            cell = progress_map.get((sid, c["id"]), {"visited": False, "quiz_score": None, "last_seen_at": None})
            fc   = flashcard_map.get((sid, c["id"]), {})
            ls   = cell.get("last_seen_at")
            cells[c["id"]] = {
                "visited":            bool(cell["visited"]),
                "quiz_score":         cell["quiz_score"],
                "last_seen_at":       ls.isoformat() if ls else None,
                "flashcard_pct":      fc.get("flashcard_pct"),
                "flashcard_mastered": fc.get("flashcard_mastered", 0),
                "flashcard_total":    fc.get("flashcard_total", 0),
                "quiz_attempts":          attempt_map_grid.get((sid, c["id"]), []),
                "video_blocks_total":     video_total_map.get(c["id"], 0),
                "video_blocks_watched":   video_watched_map.get((sid, c["id"]), 0),
            }
            if cell["visited"]:
                visited_count += 1
            if cell["quiz_score"] is not None:
                scores.append(cell["quiz_score"])
            if ls and (last_seen_at is None or ls > last_seen_at):
                last_seen_at = ls
        student_rows.append({
            "id":             sid,
            "name":           s["name"],
            "email":          s["email"],
            "visited_count":  visited_count,
            "avg_quiz_score": (sum(scores) / len(scores)) if scores else None,
            "last_seen_at":   last_seen_at.isoformat() if last_seen_at else None,
            "cells":          cells,
        })

    return {
        "course_id":   course_id,
        "course_name": course["name"],
        "concepts":    concept_list,
        "students":    student_rows,
    }


class UpdateCourseRequest(BaseModel):
    name:        str | None = None
    description: str | None = None
    subject:     str | None = None
    grade:       str | None = None
    board:       str | None = None
    status:      str | None = None


@router.patch("/{course_id}")
async def update_course(course_id: str, req: UpdateCourseRequest, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    sets, params = [], [course_id, teacher_id]
    for field, val in req.model_dump(exclude_none=True).items():
        params.append(val)
        sets.append(f"{field} = ${len(params)}")
    if not sets:
        raise HTTPException(400, "Nothing to update")
    async with get_db() as db:
        await db.execute(
            f"UPDATE courses SET {', '.join(sets)} WHERE id = $1::uuid AND teacher_id = $2::uuid",
            *params,
        )
    return {"ok": True}


@router.delete("/{course_id}")
async def delete_course(course_id: str, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "DELETE FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
    return {"ok": True}


# ── Units ─────────────────────────────────────────────────────────────────────

class UnitRequest(BaseModel):
    title:       str
    description: str | None = None
    position:    int | None = None


@router.post("/{course_id}/units")
async def add_unit(course_id: str, req: UnitRequest, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        if not course:
            raise HTTPException(404, "Course not found")

        if req.position is None:
            max_pos = await db.fetchval(
                "SELECT COALESCE(MAX(position), -1) FROM course_units WHERE course_id = $1::uuid", course_id
            )
            req.position = int(max_pos) + 1

        row = await db.fetchrow("""
            INSERT INTO course_units (course_id, title, description, position)
            VALUES ($1::uuid, $2, $3, $4)
            RETURNING id, title, description, position
        """, course_id, req.title, req.description, req.position)
    return {"id": str(row["id"]), "title": row["title"], "description": row["description"],
            "position": row["position"], "concepts": []}


@router.patch("/units/{unit_id}")
async def update_unit(unit_id: str, req: UnitRequest, authorization: str = Header(...)):
    await _require_teacher(authorization)
    sets, params = [], [unit_id]
    for field, val in req.model_dump(exclude_none=True).items():
        params.append(val)
        sets.append(f"{field} = ${len(params)}")
    if not sets:
        raise HTTPException(400, "Nothing to update")
    async with get_db() as db:
        await db.execute(
            f"UPDATE course_units SET {', '.join(sets)} WHERE id = $1::uuid", *params
        )
    return {"ok": True}


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute("DELETE FROM course_units WHERE id = $1::uuid", unit_id)
    return {"ok": True}


# ── Concepts ──────────────────────────────────────────────────────────────────

class ConceptRequest(BaseModel):
    title:       str
    description: str | None = None
    position:    int | None = None


@router.post("/units/{unit_id}/concepts")
async def add_concept(unit_id: str, req: ConceptRequest, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        if req.position is None:
            max_pos = await db.fetchval(
                "SELECT COALESCE(MAX(position), -1) FROM course_concepts WHERE unit_id = $1::uuid", unit_id
            )
            req.position = int(max_pos) + 1

        row = await db.fetchrow("""
            INSERT INTO course_concepts (unit_id, title, description, position, source)
            VALUES ($1::uuid, $2, $3, $4, 'manual')
            RETURNING id, title, description, position, study_set_id
        """, unit_id, req.title, req.description, req.position)
    return {
        "id": str(row["id"]), "title": row["title"],
        "description": row["description"], "position": row["position"],
        "study_set_id": None,
    }


@router.patch("/concepts/{concept_id}")
async def update_concept(concept_id: str, req: ConceptRequest, authorization: str = Header(...)):
    await _require_teacher(authorization)
    sets, params = [], [concept_id]
    for field, val in req.model_dump(exclude_none=True).items():
        params.append(val)
        sets.append(f"{field} = ${len(params)}")
    if not sets:
        raise HTTPException(400, "Nothing to update")
    async with get_db() as db:
        await db.execute(
            f"UPDATE course_concepts SET {', '.join(sets)} WHERE id = $1::uuid", *params
        )
    return {"ok": True}


@router.delete("/concepts/{concept_id}")
async def delete_concept(concept_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute("DELETE FROM course_concepts WHERE id = $1::uuid", concept_id)
    return {"ok": True}


@router.post("/concepts/{concept_id}/generate-suggested-prompts")
async def generate_suggested_prompts(
    concept_id: str, bg: BackgroundTasks, authorization: str = Header(...)
):
    """
    Teacher endpoint: (re)generate AI teaching prompt suggestions for a concept.
    Returns immediately; generation runs in the background.
    """
    await _require_teacher(authorization)
    bg.add_task(_generate_suggested_prompts_bg, concept_id)
    return {"ok": True, "message": "Generating suggestions in background"}


@router.post("/concepts/{concept_id}/summarize")
async def summarize_concept(
    concept_id:    str,
    bg:            BackgroundTasks,
    authorization: str = Header(...),
):
    """On-demand 'Generate explanation' — works for any concept (AI or manual-origin),
    any time. Unlocks audio/video generation once it completes."""
    await _require_teacher(authorization)
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.source_text, c.subject
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")
    if not concept["source_text"]:
        raise HTTPException(400, "This concept has no source text yet")

    async with get_db() as db:
        await db.execute(
            "UPDATE course_concepts SET pipeline_status = 'summarizing' WHERE id = $1::uuid", concept_id
        )
    bg.add_task(_summarize_one_concept, concept_id, {"subject": concept["subject"]})
    return {"ok": True, "pipeline_status": "summarizing"}


# ── Per-concept authoring chat (teacher-only — never shown to students) ───────

class ConceptChatMessage(BaseModel):
    message:          str
    image_data_url:   str | None       = None  # legacy single image
    image_data_urls:  list[str] | None = None  # multiple PDF pages as context
    image_page_nums:  list[int] | None = None  # page numbers, stored for display on reload


@router.get("/concepts/{concept_id}/concept-chat")
async def get_concept_chat(concept_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        conv = await db.fetchrow(
            "SELECT id FROM conversations WHERE concept_id = $1::uuid", concept_id
        )
        if not conv:
            return []
        rows = await db.fetch("""
            SELECT id, role, content, metadata, created_at FROM messages
            WHERE conversation_id = $1::uuid ORDER BY created_at
        """, conv["id"])
    import json as _json
    # Batch-fetch video info for any video-card messages
    video_block_ids = []
    meta_video_ids_by_block: dict[str, int] = {}  # block_id -> video_id stored in metadata
    for r in rows:
        if r["metadata"]:
            try:
                meta = r["metadata"] if isinstance(r["metadata"], dict) else _json.loads(r["metadata"])
                if meta.get("content_type") == "video" and meta.get("block_id"):
                    bid = meta["block_id"]
                    video_block_ids.append(bid)
                    if meta.get("video_id"):
                        meta_video_ids_by_block[bid] = int(meta["video_id"])
            except Exception:
                pass
    block_video_map: dict = {}
    if video_block_ids:
        async with get_db() as db2:
            brows = await db2.fetch("""
                SELECT ccb.id::text AS block_id, ccb.video_id, ccb.in_textbook,
                       v.status     AS video_status,
                       v.video_url  AS video_url,
                       v.error_message AS video_error
                FROM concept_content_blocks ccb
                LEFT JOIN videos v ON v.id = ccb.video_id
                WHERE ccb.id = ANY($1::uuid[])
            """, video_block_ids)
        block_video_map = {r["block_id"]: dict(r) for r in brows}

    # Fallback: for blocks that were deleted, recover video info via video_id stored in metadata
    orphan_video_ids = [
        vid_id for block_id, vid_id in meta_video_ids_by_block.items()
        if block_id not in block_video_map
    ]
    fallback_video_map: dict = {}
    if orphan_video_ids:
        async with get_db() as db3:
            vrows = await db3.fetch("""
                SELECT id AS video_id, status AS video_status, video_url, error_message AS video_error
                FROM videos WHERE id = ANY($1::int[])
            """, orphan_video_ids)
        fallback_video_map = {r["video_id"]: dict(r) for r in vrows}

    # Fetch message IDs that have already been imported into the textbook via apply
    async with get_db() as db_imp:
        imp_rows = await db_imp.fetch("""
            SELECT DISTINCT source_message_id::text
            FROM concept_content_blocks
            WHERE concept_id = $1::uuid
              AND source_message_id IS NOT NULL
              AND in_textbook = true
        """, concept_id)
    imported_msg_ids = {r["source_message_id"] for r in imp_rows}

    result = []
    for r in rows:
        suggestions    = []
        image_pages:   list[int] = []
        video_block_id  = ""
        video_source_id = ""
        video_int_id:    int | None = None
        video_status     = ""
        video_url        = ""
        video_error      = ""
        video_in_textbook: bool | None = None
        if r["metadata"]:
            try:
                meta = r["metadata"] if isinstance(r["metadata"], dict) else _json.loads(r["metadata"])
                suggestions = meta.get("suggestions", [])
                image_pages = meta.get("image_page_nums", [])
                if meta.get("content_type") == "video":
                    video_block_id  = meta.get("block_id", "")
                    video_source_id = meta.get("source_msg_id", "")
                    vid_info        = block_video_map.get(video_block_id, {})
                    if not vid_info:
                        # Content block deleted — recover from video_id stored in metadata
                        fallback_vid = meta.get("video_id")
                        if fallback_vid:
                            vid_info = fallback_video_map.get(int(fallback_vid), {})
                        # Signal to frontend that the content block is gone
                        if vid_info:
                            video_block_id = ""
                    video_int_id      = vid_info.get("video_id") or meta.get("video_id")
                    raw_status        = vid_info.get("video_status") or ""
                    # Normalize: videos table uses 'completed', frontend uses 'ready'
                    video_status      = "ready" if raw_status == "completed" else raw_status
                    video_url         = vid_info.get("video_url")   or ""
                    video_error       = vid_info.get("video_error") or ""
                    # None = block deleted; True/False = whether block is in textbook
                    video_in_textbook = vid_info.get("in_textbook") if vid_info else None
            except Exception:
                pass
        msg_id_str = str(r["id"])
        entry: dict = {
            "id":          msg_id_str,
            "role":        r["role"],
            "content":     r["content"],
            "suggestions": suggestions,
            "created_at":  r["created_at"].isoformat(),
            "inTextbook":  msg_id_str in imported_msg_ids,
        }
        if image_pages:
            entry["imagePages"] = image_pages
        if video_block_id or video_source_id:
            # Always include videoBlockId for video-card messages so the frontend
            # can identify them; empty string means the content block was deleted.
            # video_source_id is absent for wand-generated standalone video cards.
            entry["videoBlockId"] = video_block_id
            if video_source_id:
                entry["videoSourceMsgId"] = video_source_id
        if video_int_id is not None:
            entry["videoId"] = video_int_id
        if video_status:
            entry["videoStatus"] = video_status
        if video_url:
            entry["videoUrl"] = video_url
        if video_error:
            entry["videoError"] = video_error
        if video_in_textbook is not None:
            entry["videoInTextbook"] = video_in_textbook
        result.append(entry)
    return result


@router.post("/concepts/{concept_id}/concept-chat")
async def send_concept_chat_message(
    concept_id:    str,
    req:           ConceptChatMessage,
    authorization: str = Header(...),
):
    """
    Teacher-only authoring chat for a concept — ask AI to draft a summary/transcript,
    request revisions, give style examples. Grounded in source_text (+ full chapter
    text if available) and the concept's cropped image (if any), so the AI can
    actually see diagrams that plain OCR'd text loses (e.g. a diagonal-sum grid).
    Never shown to students.
    """
    teacher_id = await _require_teacher(authorization)
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.title, cc.source_text, cc.chapter_ref, c.subject
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
        teacher_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", teacher_id)
    if not concept:
        raise HTTPException(404, "Concept not found")

    teacher_language = teacher_lang or 'en'

    async with get_db() as db:
        conv = await db.fetchrow(
            "SELECT id FROM conversations WHERE concept_id = $1::uuid", concept_id
        )
        if not conv:
            conv = await db.fetchrow("""
                INSERT INTO conversations (user_id, title, subject, concept_id, conversation_type)
                VALUES ($1::uuid, $2, $3, $4::uuid, 'studio') RETURNING id
            """, teacher_id, f"{concept['title']} — Authoring chat", concept["subject"], concept_id)
        conv_id = conv["id"]

        history = await db.fetch("""
            SELECT role, content FROM messages WHERE conversation_id = $1::uuid ORDER BY created_at
        """, conv_id)

        image_row = await db.fetchrow("""
            SELECT data, mime_type FROM concept_images
            WHERE concept_id = $1::uuid ORDER BY position LIMIT 1
        """, concept_id)

        import json as _json
        _user_meta = {}
        if req.image_page_nums:
            _user_meta["image_page_nums"] = req.image_page_nums
        user_msg_row = await db.fetchrow(
            "INSERT INTO messages (conversation_id, role, content, metadata) VALUES ($1::uuid, 'user', $2, $3::jsonb) RETURNING id",
            conv_id, req.message, _json.dumps(_user_meta) if _user_meta else None,
        )

    # Ground in the chapter's full text if available, else just the concept's own excerpt
    material_text = concept["source_text"] or ""
    if concept["chapter_ref"]:
        async with get_db() as db:
            chapter = await db.fetchrow(
                "SELECT pdf_data FROM course_chapters WHERE id = $1::uuid", concept["chapter_ref"]
            )
        if chapter and chapter["pdf_data"]:
            from services.studyset_processor import extract_text_from_pdf
            full_text, _ = extract_text_from_pdf(bytes(chapter["pdf_data"]))
            if full_text:
                material_text = full_text

    concept_lang_note = ""
    if teacher_language in _LANGUAGE_NAMES:
        lang_name = _LANGUAGE_NAMES[teacher_language]
        concept_lang_note = f"\n\nIMPORTANT: Write ALL content in {lang_name}. Do not use English."

    system_prompt = f"""You are helping a teacher draft and refine the student-facing explanation for one
concept in their course. This conversation is teacher-only — students never see it.

Concept: {concept['title']}
Subject: {concept['subject'] or 'General'}

Source material (the textbook content this concept is based on):
---
{material_text[:40_000]}
---

Help the teacher draft, revise, and improve content for this concept. Ground everything in
the source material above — and in the attached image, if one is provided, which may show a
diagram or worked example that plain text can't fully capture.

Whenever the teacher asks for a draft or a full revision, respond with exactly these two sections:

### SUMMARY
<3-4 paragraphs, plain-language, student-friendly. If the concept involves calculations or worked examples, use the structured format: state the problem, list given values, show the formula, show each substitution step with actual numbers including the unrounded intermediate result, then the final answer with units.>

### TRANSCRIPT
<a short spoken-style narration script that reads out formulas and calculation steps aloud>

Math formatting: use $...$ for inline math and $$...$$ for display equations. Never use \\[...\\] or bare brackets. Preserve all domain-specific notation verbatim (→ ⇌ (aq) (s) mol J N m³).

For anything else (questions, brainstorming, partial feedback), just respond conversationally —
only use the SUMMARY/TRANSCRIPT format when giving a full draft the teacher can apply.

IMPORTANT: At the very end of EVERY response, append this block on its own line with no surrounding text:
<suggestions>["short follow-up 1", "short follow-up 2", "short follow-up 3"]</suggestions>
Make the suggestions specific to what you just said — they should feel like natural next steps.
Keep each suggestion under 8 words. Do not mention this block in your visible response.{concept_lang_note}"""

    ai_messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        ai_messages.append({"role": h["role"], "content": h["content"]})

    # Build image list: explicit page URLs first, then legacy single URL, then stored concept image.
    image_urls: list[str] = list(req.image_data_urls or [])
    if not image_urls and req.image_data_url:
        image_urls = [req.image_data_url]
    if not image_urls and image_row:
        b64 = base64.b64encode(bytes(image_row["data"])).decode("utf-8")
        image_urls = [f"data:{image_row['mime_type']};base64,{b64}"]

    user_content: object = req.message
    if image_urls:
        user_content = [
            *[{"type": "image_url", "image_url": {"url": u}} for u in image_urls],
            {"type": "text", "text": req.message},
        ]
    ai_messages.append({"role": "user", "content": user_content})

    from openai import AsyncOpenAI
    import json as _json
    import re as _re
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=ai_messages,
        max_tokens=2000,
        temperature=0.5,
    )
    raw_reply = response.choices[0].message.content or ""

    # Extract <suggestions>[...]</suggestions> — strip from visible content, store in metadata
    suggestions: list[str] = []
    _sugg_match = _re.search(r'<suggestions>\s*(\[.*?\])\s*</suggestions>', raw_reply, _re.DOTALL)
    if _sugg_match:
        try:
            suggestions = _json.loads(_sugg_match.group(1))
            suggestions = [s for s in suggestions if isinstance(s, str)][:4]
        except Exception:
            suggestions = []
    reply = _re.sub(r'\s*<suggestions>.*?</suggestions>', '', raw_reply, flags=_re.DOTALL).rstrip()

    metadata = _json.dumps({"suggestions": suggestions}) if suggestions else None

    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO messages (conversation_id, role, content, metadata)
            VALUES ($1::uuid, 'assistant', $2, $3::jsonb)
            RETURNING id, created_at
        """, conv_id, reply, metadata)

    return {
        "user_message_id": str(user_msg_row["id"]),
        "id":              str(row["id"]),
        "role":            "assistant",
        "content":         reply,
        "suggestions":     suggestions,
        "created_at":      row["created_at"].isoformat(),
    }


class ApplyChatRequest(BaseModel):
    message_id: str
    action:     str = 'block'  # 'block' | 'summary' | 'transcript'


_CHAT_SUMMARY_RE    = re.compile(r'^\s*#{0,6}\s*\*{0,2}SUMMARY\*{0,2}\s*:?\s*$',    re.IGNORECASE | re.MULTILINE)
_CHAT_TRANSCRIPT_RE = re.compile(r'^\s*#{0,6}\s*\*{0,2}TRANSCRIPT\*{0,2}\s*:?\s*$', re.IGNORECASE | re.MULTILINE)


@router.post("/concepts/{concept_id}/concept-chat/apply")
async def apply_concept_chat_message(
    concept_id:    str,
    req:           ApplyChatRequest,
    bg:            BackgroundTasks,
    authorization: str = Header(...),
):
    """Apply a Studio message: add to Textbook ('block'), set as summary, or set as transcript."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT m.content, m.role
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = $1::uuid AND c.concept_id = $2::uuid
        """, req.message_id, concept_id)
    if not row or row["role"] != "assistant":
        raise HTTPException(404, "Message not found")

    content = row["content"]

    if req.action == 'block':
        summary_match    = _CHAT_SUMMARY_RE.search(content)
        transcript_match = _CHAT_TRANSCRIPT_RE.search(content)

        # audio_script: formula-free transcript text used as TTS source on the summary block
        auto_audio_script: str | None = None

        if summary_match and transcript_match:
            # Two distinct sections — Summary → textbook block, Transcript → audio only
            summary_body    = content[summary_match.end():transcript_match.start()].strip()
            transcript_body = content[transcript_match.end():].strip()
            auto_audio_script = transcript_body or None

            async with get_db() as db:
                prev_q = await db.fetchrow("""
                    SELECT m.content FROM messages m
                    JOIN conversations c ON c.id = m.conversation_id
                    WHERE c.concept_id = $1::uuid
                      AND m.role = 'user'
                      AND m.created_at < (SELECT created_at FROM messages WHERE id = $2::uuid)
                    ORDER BY m.created_at DESC LIMIT 1
                """, concept_id, req.message_id)
            if prev_q and prev_q["content"]:
                q = prev_q["content"].strip().rstrip("?").strip()
                if len(q) > 120:
                    q = q[:120].rsplit(" ", 1)[0] + "…"
                heading_body = f"## {q}"
            else:
                heading_body = None

            # blocks: (title, body, audio_script) — transcript becomes audio, NOT a separate block
            blocks_to_insert: list[tuple[str | None, str, str | None]] = []
            if heading_body:
                blocks_to_insert.append((None, heading_body, None))
            blocks_to_insert.append(("Summary", summary_body, auto_audio_script))
        else:
            # Single-section message → one block, strip any stray header
            body = _CHAT_SUMMARY_RE.sub('', content)
            body = _CHAT_TRANSCRIPT_RE.sub('', body).strip()
            blocks_to_insert = [(None, body, None)]

        async with get_db() as db:
            max_pos = await db.fetchval(
                "SELECT COALESCE(MAX(position), -1) FROM concept_content_blocks WHERE concept_id = $1::uuid",
                concept_id,
            )
            first_block = None
            audio_block_id: str | None = None
            for i, (blk_title, blk_body, blk_audio_script) in enumerate(blocks_to_insert):
                blk_audio_status = 'generating' if blk_audio_script else 'none'
                block = await db.fetchrow("""
                    INSERT INTO concept_content_blocks
                      (concept_id, type, position, title, body, created_by,
                       audio_script, audio_status, source_message_id)
                    VALUES ($1::uuid, 'text', $2, $3, $4, $5::uuid, $6, $7, $8::uuid)
                    RETURNING id, type, position, title, body, audio_status, created_at
                """, concept_id, int(max_pos) + 1 + i, blk_title, blk_body, teacher_id,
                    blk_audio_script, blk_audio_status, req.message_id)
                if blk_audio_script:
                    audio_block_id = str(block["id"])
                if first_block is None:
                    first_block = block
            # Silently set ai_summary if not yet populated — powers quiz/flashcard generation
            existing_summary = await db.fetchval(
                "SELECT ai_summary FROM course_concepts WHERE id = $1::uuid", concept_id
            )
            if not existing_summary or not existing_summary.strip():
                await db.execute(
                    "UPDATE course_concepts SET ai_summary = $1, pipeline_status = 'ready' WHERE id = $2::uuid",
                    blocks_to_insert[0][1], concept_id,
                )

        # Auto-generate audio from the transcript for the summary block
        if audio_block_id:
            bg.add_task(_generate_block_audio_bg, concept_id, audio_block_id)
        block = first_block
        return {
            "action":       "block",
            "id":           str(block["id"]),
            "type":         block["type"],
            "position":     block["position"],
            "title":        block["title"],
            "body":         block["body"],
            "audio_status": block["audio_status"],
            "created_at":   block["created_at"].isoformat(),
            "blocks_added": len(blocks_to_insert),
        }

    # 'summary' or 'transcript' — extract the relevant section from the message
    summary_match    = _CHAT_SUMMARY_RE.search(content)
    transcript_match = _CHAT_TRANSCRIPT_RE.search(content)

    if req.action == 'summary':
        if summary_match and transcript_match:
            text = content[summary_match.end():transcript_match.start()].strip()
        elif summary_match:
            text = content[summary_match.end():].strip()
        else:
            text = content.strip()
        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET ai_summary = $1, pipeline_status = 'ready' WHERE id = $2::uuid",
                text, concept_id,
            )
        return {"action": "summary", "ai_summary": text}

    if req.action == 'transcript':
        if transcript_match:
            text = content[transcript_match.end():].strip()
        elif summary_match:
            text = content[summary_match.end():].strip()
        else:
            text = content.strip()
        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET ai_transcript = $1 WHERE id = $2::uuid",
                text, concept_id,
            )
        return {"action": "transcript", "ai_transcript": text}

    raise HTTPException(400, "action must be 'block', 'summary', or 'transcript'")


class GenerateChatVideoRequest(BaseModel):
    title: str | None = None


@router.post("/concepts/{concept_id}/concept-chat/{source_msg_id}/generate-video")
async def generate_chat_video_from_message(
    concept_id:    str,
    source_msg_id: str,
    req:           GenerateChatVideoRequest,
    bg:            BackgroundTasks,
    authorization: str = Header(...),
):
    """
    Start video generation from a Studio chat assistant message and insert a
    video card into the conversation so the teacher can track progress inline.
    """
    teacher_id = await _require_teacher(authorization)

    async with get_db() as db:
        msg = await db.fetchrow("""
            SELECT m.id, m.content, m.conversation_id
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = $1::uuid AND c.concept_id = $2::uuid AND m.role = 'assistant'
        """, source_msg_id, concept_id)
    if not msg:
        raise HTTPException(404, "Message not found")

    transcript = (msg["content"] or "").strip()
    if not transcript:
        raise HTTPException(400, "Message is empty — cannot generate video")

    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT c.subject FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")

    title = (req.title or "").strip() or "Video"

    import json as _json

    async with get_db() as db:
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM concept_content_blocks WHERE concept_id = $1::uuid",
            concept_id,
        )
        block = await db.fetchrow("""
            INSERT INTO concept_content_blocks
              (concept_id, type, position, title, body, created_by, in_textbook)
            VALUES ($1::uuid, 'video', $2, $3, $4, $5::uuid, false)
            RETURNING id, position, title, created_at
        """, concept_id, int(max_pos) + 1, title, transcript, teacher_id)

    block_id = str(block["id"])
    bg.add_task(
        _generate_block_video_bg,
        block_id, concept_id, title, transcript, concept["subject"], teacher_id,
    )

    card_meta = _json.dumps({
        "content_type": "video",
        "block_id": block_id,
        "source_msg_id": source_msg_id,
    })

    async with get_db() as db:
        card = await db.fetchrow("""
            INSERT INTO messages (conversation_id, role, content, metadata)
            VALUES ($1::uuid, 'assistant', '', $2::jsonb)
            RETURNING id, created_at
        """, msg["conversation_id"], card_meta)

    return {
        "id":               str(card["id"]),
        "role":             "assistant",
        "content":          "",
        "suggestions":      [],
        "created_at":       card["created_at"].isoformat(),
        "videoBlockId":     block_id,
        "videoStatus":      "pending",
        "videoSourceMsgId": source_msg_id,
        "videoInTextbook":  False,
    }


# ── Concept content blocks (textbook-style ordered blocks per concept) ────────

class ContentBlockRequest(BaseModel):
    type:     str       = 'text'   # 'text' | 'video'
    title:    str | None = None
    body:     str | None = None
    video_id: int | None = None
    position: int | None = None


@router.get("/concepts/{concept_id}/content-blocks")
async def list_content_blocks(concept_id: str, authorization: str = Header(...)):
    """List content blocks ordered by position — readable by students and teachers."""
    await _get_student(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT cb.id, cb.type, cb.position, cb.title, cb.body,
                   cb.video_id, v.video_url, v.status AS video_status,
                   cb.audio_status, (cb.audio_data IS NOT NULL) AS has_audio,
                   cb.created_at
            FROM concept_content_blocks cb
            LEFT JOIN videos v ON v.id = cb.video_id
            WHERE cb.concept_id = $1::uuid AND cb.in_textbook = true
            ORDER BY cb.position, cb.created_at
        """, concept_id)
    return [
        {
            "id":           str(r["id"]),
            "type":         r["type"],
            "position":     r["position"],
            "title":        r["title"],
            "body":         r["body"],
            "video_id":     r["video_id"],
            "video_url":    r["video_url"],
            "video_status": r["video_status"],
            "audio_status": r["audio_status"],
            "has_audio":    r["has_audio"],
            "created_at":   r["created_at"].isoformat(),
        }
        for r in rows
    ]


@router.post("/concepts/{concept_id}/content-blocks")
async def add_content_block(
    concept_id:    str,
    req:           ContentBlockRequest,
    authorization: str = Header(...),
):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        if req.position is None:
            max_pos = await db.fetchval(
                "SELECT COALESCE(MAX(position), -1) FROM concept_content_blocks WHERE concept_id = $1::uuid",
                concept_id,
            )
            req.position = int(max_pos) + 1
        row = await db.fetchrow("""
            INSERT INTO concept_content_blocks
              (concept_id, type, position, title, body, video_id, created_by)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::uuid)
            RETURNING id, type, position, title, body, video_id, created_at
        """, concept_id, req.type, req.position, req.title, req.body,
            req.video_id, teacher_id)
    return {
        "id":       str(row["id"]),
        "type":     row["type"],
        "position": row["position"],
        "title":    row["title"],
        "body":     row["body"],
        "video_id": row["video_id"],
        "created_at": row["created_at"].isoformat(),
    }


class UpdateBlockRequest(BaseModel):
    title:    str | None = None
    body:     str | None = None
    position: int | None = None


@router.patch("/concepts/{concept_id}/content-blocks/{block_id}")
async def update_content_block(
    concept_id:    str,
    block_id:      str,
    req:           UpdateBlockRequest,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    sets, params = [], [block_id, concept_id]
    for field, val in req.model_dump(exclude_none=True).items():
        params.append(val)
        sets.append(f"{field} = ${len(params)}")
    if not sets:
        raise HTTPException(400, "Nothing to update")
    async with get_db() as db:
        await db.execute(
            f"UPDATE concept_content_blocks SET {', '.join(sets)} WHERE id = $1::uuid AND concept_id = $2::uuid",
            *params,
        )
    return {"ok": True}


@router.delete("/concepts/{concept_id}/content-blocks/{block_id}")
async def delete_content_block(
    concept_id:    str,
    block_id:      str,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "DELETE FROM concept_content_blocks WHERE id = $1::uuid AND concept_id = $2::uuid",
            block_id, concept_id,
        )
    return {"ok": True}


class BlockReorderItem(BaseModel):
    id:       str
    position: int

@router.post("/concepts/{concept_id}/content-blocks/reorder")
async def reorder_content_blocks(
    concept_id:    str,
    items:         list[BlockReorderItem],
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    async with get_db() as db:
        for item in items:
            await db.execute(
                "UPDATE concept_content_blocks SET position = $1 WHERE id = $2::uuid AND concept_id = $3::uuid",
                item.position, item.id, concept_id,
            )
    return {"ok": True}


@router.get("/concepts/{concept_id}/content-blocks/{block_id}/status")
async def get_block_video_status(
    concept_id:    str,
    block_id:      str,
    authorization: str = Header(...),
):
    """Poll the current video generation status for a content block."""
    await _require_teacher(authorization)
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT cb.video_id, v.status AS video_status, v.video_url, v.error_message
            FROM concept_content_blocks cb
            LEFT JOIN videos v ON v.id = cb.video_id
            WHERE cb.id = $1::uuid AND cb.concept_id = $2::uuid
        """, block_id, concept_id)
    if not row:
        raise HTTPException(404, "Block not found")
    return {
        "video_id":     row["video_id"],
        "video_status": row["video_status"] or "pending",
        "video_url":    row["video_url"],
        "video_error":  row["error_message"],
    }


@router.post("/concepts/{concept_id}/content-blocks/{block_id}/add-to-textbook")
async def add_block_to_textbook(
    concept_id:    str,
    block_id:      str,
    authorization: str = Header(...),
):
    """Mark a studio-generated video block as visible in the textbook and move it to the end."""
    await _require_teacher(authorization)
    async with get_db() as db:
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM concept_content_blocks WHERE concept_id = $1::uuid",
            concept_id,
        )
        row = await db.fetchrow("""
            UPDATE concept_content_blocks
            SET in_textbook = true, position = $1
            WHERE id = $2::uuid AND concept_id = $3::uuid
            RETURNING id, position, in_textbook
        """, int(max_pos) + 1, block_id, concept_id)
    if not row:
        raise HTTPException(404, "Block not found")
    return {"id": str(row["id"]), "position": row["position"], "in_textbook": row["in_textbook"]}


@router.post("/concepts/{concept_id}/content-blocks/{block_id}/retry-video")
async def retry_block_video(
    concept_id:    str,
    block_id:      str,
    bg:            BackgroundTasks,
    authorization: str = Header(...),
):
    """Retry a failed video generation for a content block."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        block = await db.fetchrow(
            "SELECT id, title, body FROM concept_content_blocks WHERE id = $1::uuid AND concept_id = $2::uuid AND type = 'video'",
            block_id, concept_id,
        )
        if not block:
            raise HTTPException(404, "Block not found")
        concept = await db.fetchrow("""
            SELECT c.subject FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
        await db.execute(
            "UPDATE concept_content_blocks SET video_id = NULL WHERE id = $1::uuid", block_id,
        )
    bg.add_task(
        _generate_block_video_bg,
        block_id, concept_id, block["title"] or "", block["body"] or "",
        concept["subject"] if concept else None, teacher_id,
    )
    return {"video_status": "pending"}


async def _generate_block_audio_bg(concept_id: str, block_id: str):
    """Background: TTS via OpenAI — converts a content block's body to MP3 and stores as bytea."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    try:
        async with get_db() as db:
            block = await db.fetchrow(
                "SELECT body, title, audio_script FROM concept_content_blocks WHERE id = $1::uuid AND concept_id = $2::uuid",
                block_id, concept_id,
            )
        if not block:
            return
        # audio_script is the formula-free transcript; fall back to body for plain text blocks
        script = block["audio_script"] or block["body"] or block["title"] or ""
        if not script.strip():
            async with get_db() as db:
                await db.execute(
                    "UPDATE concept_content_blocks SET audio_status = 'failed' WHERE id = $1::uuid", block_id
                )
            return
        response = await client.audio.speech.create(
            model="tts-1", voice="nova", input=script[:4096],
        )
        audio_bytes = response.content
        async with get_db() as db:
            await db.execute(
                "UPDATE concept_content_blocks SET audio_data = $1, audio_status = 'ready' WHERE id = $2::uuid",
                audio_bytes, block_id,
            )
    except Exception as exc:
        logger.error("[block-audio] block %s failed: %s", block_id, exc)
        async with get_db() as db:
            await db.execute(
                "UPDATE concept_content_blocks SET audio_status = 'failed' WHERE id = $1::uuid", block_id
            )


@router.post("/concepts/{concept_id}/content-blocks/{block_id}/generate-audio")
async def generate_block_audio(
    concept_id:    str,
    block_id:      str,
    bg:            BackgroundTasks,
    authorization: str = Header(...),
):
    """Teacher: generate TTS audio for a text content block."""
    await _require_teacher(authorization)
    async with get_db() as db:
        exists = await db.fetchval(
            "SELECT 1 FROM concept_content_blocks WHERE id = $1::uuid AND concept_id = $2::uuid",
            block_id, concept_id,
        )
    if not exists:
        raise HTTPException(404, "Block not found")
    async with get_db() as db:
        await db.execute(
            "UPDATE concept_content_blocks SET audio_status = 'generating', audio_data = NULL WHERE id = $1::uuid",
            block_id,
        )
    bg.add_task(_generate_block_audio_bg, concept_id, block_id)
    return {"audio_status": "generating"}


@router.get("/concepts/{concept_id}/content-blocks/{block_id}/audio")
async def serve_block_audio(concept_id: str, block_id: str):
    """Serve audio bytes for a content block — no auth (UUID is unguessable, <audio> can't send headers)."""
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT audio_data FROM concept_content_blocks WHERE id = $1::uuid AND concept_id = $2::uuid",
            block_id, concept_id,
        )
    if not row or not row["audio_data"]:
        raise HTTPException(404, "Audio not available")
    from fastapi.responses import Response
    audio_bytes = bytes(row["audio_data"])
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Length": str(len(audio_bytes)), "Accept-Ranges": "bytes"},
    )


# ── Teacher Studio: chapter-level authoring chat ──────────────────────────────

class StudioChatRequest(BaseModel):
    message:        str
    history:        list[dict] | None = None  # [{role, content}]
    image_data_url: str | None        = None  # PNG/JPEG clip base64-encoded


@router.post("/chapters/{chapter_id}/studio-chat")
async def studio_chat(
    chapter_id:    str,
    req:           StudioChatRequest,
    authorization: str = Header(...),
):
    """
    Teacher authoring chat grounded in the full chapter text.
    Accepts an optional image clip (base64 PNG) so the teacher can ask about
    a specific region of the PDF. Returns an AI response that may contain
    ### EXPLANATION and ### VIDEO SCRIPT sections for saving as content blocks.
    """
    teacher_id = await _require_teacher(authorization)
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    async with get_db() as db:
        chapter = await db.fetchrow("""
            SELECT ch.id, ch.pdf_data, ch.filename, c.name, c.subject
            FROM course_chapters ch
            JOIN courses c ON c.id = ch.course_id
            WHERE ch.id = $1::uuid
        """, chapter_id)
        teacher_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", teacher_id)

    if not chapter:
        raise HTTPException(404, "Chapter not found")

    material_text = ""
    if chapter["pdf_data"]:
        from services.studyset_processor import extract_text_from_pdf
        material_text, _ = extract_text_from_pdf(bytes(chapter["pdf_data"]))

    teacher_language = teacher_lang or 'en'
    lang_note = ""
    if teacher_language in _LANGUAGE_NAMES:
        lang_note = f"\n\nIMPORTANT: Write ALL content in {_LANGUAGE_NAMES[teacher_language]}. Do not use English."

    system_prompt = f"""You are helping a teacher create educational content for their course. You have access to the full chapter text, and optionally a cropped region from the PDF that the teacher has highlighted.

Course: {chapter['name']}
Subject: {chapter['subject'] or 'General'}
Chapter: {chapter['filename']}

Chapter text:
---
{material_text[:40_000]}
---

Help the teacher draft explanations and video scripts for their students. When giving a full draft, use these section headers exactly:

### EXPLANATION
<3-4 paragraph student-facing written explanation>

### VIDEO SCRIPT
<short spoken narration script, 60-90 seconds when read aloud>

For conversational questions or partial feedback, just respond naturally — only use the headers when giving a full draft the teacher can save.{lang_note}"""

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for h in (req.history or []):
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})

    user_content: object = req.message
    if req.image_data_url:
        try:
            header, b64data = req.image_data_url.split(",", 1)
            mime = "image/png" if "image/png" in header else "image/jpeg"
            user_content = [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64data}"}},
                {"type": "text", "text": req.message},
            ]
        except Exception:
            pass
    messages.append({"role": "user", "content": user_content})

    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=2000,
        temperature=0.5,
    )
    reply = response.choices[0].message.content
    return {"role": "assistant", "content": reply}


# ── Syllabus import ───────────────────────────────────────────────────────────

@router.post("/{course_id}/import-syllabus")
async def import_syllabus(
    course_id:     str,
    authorization: str        = Header(...),
    file:          UploadFile = File(...),
):
    """
    Upload a syllabus PDF → extract units + concepts via GPT-4o.
    Returns a preview; nothing is saved yet.
    Call /confirm-import to persist.
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id, name, subject, grade, board FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        teacher_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", teacher_id)
    if not course:
        raise HTTPException(404, "Course not found")

    teacher_language = teacher_lang or 'en'

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(400, "File too large — max 20 MB")

    from services.studyset_processor import extract_text_from_pdf
    from openai import AsyncOpenAI

    text, page_count = extract_text_from_pdf(file_bytes)
    truncated = text[:80_000]

    syllabus_lang_note = ""
    if teacher_language in _LANGUAGE_NAMES:
        syllabus_lang_note = f"\nIMPORTANT: Write ALL titles and descriptions in {_LANGUAGE_NAMES[teacher_language]}."

    client = AsyncOpenAI()
    _syl_grade = f"\nGrade: {course['grade']}" if course.get("grade") else ""
    _syl_board = f"\nCurriculum Board: {course['board']}" if course.get("board") else ""
    prompt = f"""You are an expert curriculum designer. Analyze the syllabus/textbook below and extract a structured course outline.

Course name: {course["name"]}
Subject: {course["subject"] or "General"}{_syl_grade}{_syl_board}

Return ONLY valid JSON — no prose, no markdown fences:
{{
  "units": [
    {{
      "title": "Unit title",
      "description": "1-2 sentence description of this unit",
      "concepts": [
        {{
          "title": "Concept or topic name",
          "description": "1 sentence description"
        }}
      ]
    }}
  ]
}}

Requirements:
- Extract 4-10 units (major chapters or topic groups)
- Each unit should have 3-8 concepts (specific topics, subtopics)
- Titles should be concise and student-friendly
- Follow the order as it appears in the syllabus{syllabus_lang_note}

--- SYLLABUS ---
{truncated}"""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=4000,
        temperature=0.2,
    )

    result = json.loads(response.choices[0].message.content)
    units = result.get("units", [])

    # Persist the PDF so teachers can reference it in the concept editor
    async with get_db() as db:
        await db.execute(
            "UPDATE courses SET syllabus_pdf = $1, syllabus_filename = $2 WHERE id = $3::uuid",
            file_bytes, file.filename, course_id,
        )

    return {
        "page_count":    page_count,
        "unit_count":    len(units),
        "concept_count": sum(len(u.get("concepts", [])) for u in units),
        "units":         units,
    }


class ConfirmImportRequest(BaseModel):
    units: list[dict]   # same shape returned by import-syllabus


@router.post("/{course_id}/confirm-import")
async def confirm_import(
    course_id: str,
    req:       ConfirmImportRequest,
    authorization: str = Header(...),
):
    """Persist the (possibly edited) import preview into the DB."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        if not course:
            raise HTTPException(404, "Course not found")

        # Clear existing structure
        await db.execute(
            "DELETE FROM course_units WHERE course_id = $1::uuid", course_id
        )

        for unit_pos, unit in enumerate(req.units):
            unit_row = await db.fetchrow("""
                INSERT INTO course_units (course_id, title, description, position)
                VALUES ($1::uuid, $2, $3, $4) RETURNING id
            """, course_id, unit.get("title", ""), unit.get("description"), unit_pos)

            for concept_pos, concept in enumerate(unit.get("concepts", [])):
                await db.execute("""
                    INSERT INTO course_concepts (unit_id, title, description, position)
                    VALUES ($1, $2, $3, $4)
                """, unit_row["id"], concept.get("title", ""), concept.get("description"), concept_pos)

    return {"ok": True, "unit_count": len(req.units)}


# ── Assign to classroom ───────────────────────────────────────────────────────

class AssignRequest(BaseModel):
    classroom_id: str


@router.post("/{course_id}/assign")
async def assign_to_classroom(course_id: str, req: AssignRequest, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        if not course:
            raise HTTPException(404, "Course not found")
        await db.execute("""
            INSERT INTO classroom_courses (classroom_id, course_id)
            VALUES ($1::uuid, $2::uuid) ON CONFLICT DO NOTHING
        """, req.classroom_id, course_id)
    return {"ok": True}


@router.delete("/{course_id}/assign/{classroom_id}")
async def unassign_from_classroom(course_id: str, classroom_id: str, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute("""
            DELETE FROM classroom_courses
            WHERE course_id = $1::uuid AND classroom_id = $2::uuid
            AND course_id IN (SELECT id FROM courses WHERE teacher_id = $3::uuid)
        """, course_id, classroom_id, teacher_id)
    return {"ok": True}


# ── Student: view course with progress ────────────────────────────────────────

async def _get_student(authorization: str):
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT id, is_active FROM users WHERE id = $1::uuid", user_id
        )
    if not row or not row["is_active"]:
        raise HTTPException(403, "Account inactive")
    return str(row["id"])


@router.get("/{course_id}/curriculum-context")
async def get_course_curriculum_context(course_id: str):
    """
    Returns curriculum context for a course (public — UUID is scoped to the course).
    Returns {} when no curriculum context is linked (zero effect for non-pilot courses).
    """
    from services.curriculum import get_curriculum_context
    ctx = await get_curriculum_context(course_id)
    if not ctx:
        return {}
    return {
        "id":               str(ctx.get("id")) if ctx.get("id") else None,
        "name":             ctx.get("name"),
        "driving_question": ctx.get("driving_question"),
        "teks_codes":       ctx.get("teks_codes") or [],
        "grade_level":      ctx.get("grade_level"),
        "subject":          ctx.get("subject"),
        "active_lesson":    ctx.get("active_lesson"),
        "lesson_count":     ctx.get("lesson_count"),
        "unit_start_date":  ctx.get("unit_start_date").isoformat() if ctx.get("unit_start_date") else None,
        "unit_end_date":    ctx.get("unit_end_date").isoformat() if ctx.get("unit_end_date") else None,
    }


@router.patch("/{course_id}/curriculum-context")
async def patch_course_curriculum_context(
    course_id: str,
    body: dict,
    authorization: str = Header(...),
):
    """
    Teacher endpoint: link/unlink a curriculum_context to a course, or update active_lesson.
    Body: { curriculum_context_id?: str | null, active_lesson?: int }
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
    if not course:
        raise HTTPException(404, "Course not found")

    updates = []
    params: list = []

    if "curriculum_context_id" in body:
        ctx_id = body["curriculum_context_id"]
        updates.append(f"curriculum_context_id = ${len(params)+1}")
        params.append(ctx_id)  # None = unlink

    if "active_lesson" in body:
        lesson = int(body["active_lesson"])
        # Update active_lesson on the curriculum_contexts row via the course FK
        async with get_db() as db:
            await db.execute("""
                UPDATE curriculum_contexts cc
                SET active_lesson = $1
                FROM courses c
                WHERE c.curriculum_context_id = cc.id
                  AND c.id = $2::uuid
                  AND c.teacher_id = $3::uuid
            """, lesson, course_id, teacher_id)

    if updates:
        params.append(course_id)
        async with get_db() as db:
            await db.execute(
                f"UPDATE courses SET {', '.join(updates)} WHERE id = ${len(params)}::uuid",
                *params,
            )

    return {"ok": True}


@router.post("/{course_id}/auto-rename-concepts")
async def auto_rename_concepts(course_id: str, authorization: str = Header(...)):
    """
    Teacher endpoint: uses AI to generate proper lesson-question titles for all
    concepts that still have placeholder names (e.g. 'LESSON 1', 'LESSON 2').
    Concepts without extracted source_text are skipped.
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
    if not course:
        raise HTTPException(404, "Course not found")

    async with get_db() as db:
        concepts = await db.fetch("""
            SELECT cc.id, cc.title, cc.source_text
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid
              AND cc.source_text IS NOT NULL
              AND length(trim(cc.source_text)) > 20
            ORDER BY cu.position, cc.position
        """, course_id)

    if not concepts:
        return {"renamed": 0, "concepts": []}

    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    updates = []
    for concept in concepts:
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You generate concise inquiry-style lesson titles for a science course. "
                            "Given a lesson's content, produce a single question title (8–14 words) that captures "
                            "what students will investigate — the kind of question a student would ask. "
                            "Return ONLY the title, no quotes, no explanation, no period at the end."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Current placeholder title: {concept['title']}\n\n"
                            f"Lesson content (excerpt):\n{concept['source_text'][:600]}"
                        ),
                    },
                ],
                max_tokens=40,
                temperature=0.3,
            )
            new_title = resp.choices[0].message.content.strip().strip('"').strip("'")
            if new_title:
                updates.append({"id": str(concept["id"]), "old_title": concept["title"], "new_title": new_title})
        except Exception:
            pass  # skip on failure, don't break the whole batch

    async with get_db() as db:
        for u in updates:
            await db.execute(
                "UPDATE course_concepts SET title = $1 WHERE id = $2::uuid",
                u["new_title"], u["id"],
            )

    return {"renamed": len(updates), "concepts": updates}


@router.get("/{course_id}/student")
async def get_course_student_view(course_id: str, authorization: str = Header(...)):
    """
    Student view of a course — units + concepts with their own progress overlay.
    """
    student_id = await _get_student(authorization)

    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id, name, description, subject, grade, status FROM courses WHERE id = $1::uuid",
            course_id,
        )
        if not course:
            raise HTTPException(404, "Course not found")

        units = await db.fetch("""
            SELECT id, title, description, position FROM course_units
            WHERE course_id = $1::uuid ORDER BY position, created_at
        """, course_id)

        unit_ids = [str(u["id"]) for u in units]
        concepts = []
        if unit_ids:
            concepts = await db.fetch("""
                SELECT cc.id, cc.unit_id, cc.title, cc.description,
                       cc.study_set_id, cc.position,
                       scp.visited, scp.visited_at, scp.quiz_score
                FROM course_concepts cc
                LEFT JOIN student_concept_progress scp
                       ON scp.concept_id = cc.id AND scp.student_id = $2::uuid
                WHERE cc.unit_id = ANY($1::uuid[])
                ORDER BY cc.unit_id, cc.position, cc.created_at
            """, unit_ids, student_id)

    concept_map: dict[str, list] = {uid: [] for uid in unit_ids}
    for c in concepts:
        uid = str(c["unit_id"])
        if uid in concept_map:
            concept_map[uid].append({
                "id":           str(c["id"]),
                "title":        c["title"],
                "description":  c["description"],
                "study_set_id": str(c["study_set_id"]) if c["study_set_id"] else None,
                "position":     c["position"],
                "visited":      bool(c["visited"]),
                "visited_at":   c["visited_at"].isoformat() if c["visited_at"] else None,
                "quiz_score":   c["quiz_score"],
            })

    total    = sum(len(v) for v in concept_map.values())
    visited  = sum(1 for v in concept_map.values() for c in v if c["visited"])

    return {
        **_fmt_course(course),
        "progress":      {"visited": visited, "total": total},
        "units": [
            {
                "id":          str(u["id"]),
                "title":       u["title"],
                "description": u["description"],
                "position":    u["position"],
                "concepts":    concept_map.get(str(u["id"]), []),
            }
            for u in units
        ],
    }


@router.post("/concepts/{concept_id}/activate")
async def activate_concept(concept_id: str, authorization: str = Header(...)):
    """
    Student opens a concept:
    1. Record visited progress
    2. Auto-create the seeded study set if one doesn't exist yet
    3. Sync any PDF concept_resources to study_materials for chat grounding
    Returns study_set_id for the Q&A chat.
    """
    student_id = await _get_student(authorization)

    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.title, cc.study_set_id, cc.source_text, cc.chapter_ref,
                   cu.course_id, c.subject
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id  = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)

    if not concept:
        raise HTTPException(404, "Concept not found")

    # Mark visited
    async with get_db() as db:
        await db.execute("""
            INSERT INTO student_concept_progress
              (student_id, concept_id, course_id, visited, visited_at, last_seen_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, true, NOW(), NOW())
            ON CONFLICT (student_id, concept_id)
            DO UPDATE SET visited = true, visited_at = COALESCE(student_concept_progress.visited_at, NOW()),
                          last_seen_at = NOW()
        """, student_id, concept_id, str(concept["course_id"]))

    study_set_id = concept["study_set_id"]

    # Auto-create study set from concept source material
    if not study_set_id:
        material_text = concept["source_text"] or concept["title"]
        if concept["chapter_ref"]:
            async with get_db() as db:
                chapter = await db.fetchrow(
                    "SELECT pdf_data FROM course_chapters WHERE id = $1::uuid", concept["chapter_ref"]
                )
            if chapter and chapter["pdf_data"]:
                from services.studyset_processor import extract_text_from_pdf
                full_text, _ = extract_text_from_pdf(bytes(chapter["pdf_data"]))
                if full_text:
                    material_text = full_text

        study_set_id = await _create_seeded_study_set(concept["title"], concept["subject"], material_text)
        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET study_set_id = $1::uuid WHERE id = $2::uuid",
                study_set_id, concept_id,
            )

    # Sync PDF resources not yet in study_materials
    async with get_db() as db:
        pdf_resources = await db.fetch("""
            SELECT id, title, raw_text
            FROM concept_resources
            WHERE concept_id = $1::uuid AND type = 'pdf' AND raw_text IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM study_materials sm
                WHERE sm.study_set_id = $2::uuid AND sm.filename = 'resource:' || id::text
              )
        """, concept_id, study_set_id)
        for res in pdf_resources:
            await db.execute("""
                INSERT INTO study_materials (study_set_id, filename, raw_text, char_count, status)
                VALUES ($1::uuid, $2, $3, $4, 'ready')
            """, study_set_id, f"resource:{res['id']}", res["raw_text"], len(res["raw_text"]))

    return {"study_set_id": str(study_set_id)}


class QuizScoreRequest(BaseModel):
    score: float                    # 0-100
    answers: list | None = None     # [{qi, question, chosen, correct, ok}, ...]


@router.post("/concepts/{concept_id}/quiz/score")
async def submit_quiz_score(
    concept_id: str,
    req: QuizScoreRequest,
    authorization: str = Header(...),
):
    """Record a student's quiz attempt score (0-100) for progress tracking."""
    student_id = await _get_student(authorization)
    score = max(0.0, min(100.0, req.score))

    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cu.course_id
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cc.id = $1::uuid
        """, concept_id)
        if not concept:
            raise HTTPException(404, "Concept not found")

        await db.execute("""
            INSERT INTO student_concept_progress
              (student_id, concept_id, course_id, visited, visited_at, quiz_score, quiz_taken_at, last_seen_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, true, NOW(), $4, NOW(), NOW())
            ON CONFLICT (student_id, concept_id)
            DO UPDATE SET quiz_score = $4, quiz_taken_at = NOW(),
                          visited = true, visited_at = COALESCE(student_concept_progress.visited_at, NOW()),
                          last_seen_at = NOW()
        """, student_id, concept_id, str(concept["course_id"]), score)

        # Log every attempt with per-question answers so teachers can see score trends and question stats
        import json as _json
        answers_json = _json.dumps(req.answers) if req.answers else None
        await db.execute(
            "INSERT INTO concept_quiz_attempts (student_id, concept_id, score, answers) VALUES ($1::uuid, $2::uuid, $3, $4::jsonb)",
            student_id, concept_id, score, answers_json,
        )

    return {"ok": True, "quiz_score": score}


@router.get("/concepts/{concept_id}/quiz-analytics")
async def get_quiz_analytics(concept_id: str, authorization: str = Header(...)):
    """
    Teacher-only. Aggregates per-question performance across all student attempts
    that include answer detail. Returns questions sorted hardest-first (lowest correct %).
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        # Verify teacher owns this concept
        owned = await db.fetchval("""
            SELECT 1
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id  = cu.course_id
            WHERE cc.id = $1::uuid AND c.teacher_id = $2::uuid
        """, concept_id, teacher_id)
        if not owned:
            raise HTTPException(403, "Not your concept")

        rows = await db.fetch("""
            SELECT score, answers, taken_at
            FROM concept_quiz_attempts
            WHERE concept_id = $1::uuid AND answers IS NOT NULL
            ORDER BY taken_at ASC
        """, concept_id)

    total_attempts = len(rows)
    question_stats: dict[int, dict] = {}

    for row in rows:
        answers = row["answers"]
        if not answers:
            continue
        for ans in answers:
            qi = int(ans.get("qi", 0))
            if qi not in question_stats:
                question_stats[qi] = {
                    "qi": qi,
                    "question": ans.get("question", ""),
                    "correct": 0,
                    "total": 0,
                    "wrong_tally": {},
                }
            s = question_stats[qi]
            s["total"] += 1
            if ans.get("ok"):
                s["correct"] += 1
            else:
                chosen = str(ans.get("chosen", ""))
                s["wrong_tally"][chosen] = s["wrong_tally"].get(chosen, 0) + 1

    questions = []
    for qi, s in sorted(question_stats.items()):
        most_wrong = (
            int(max(s["wrong_tally"], key=s["wrong_tally"].get))
            if s["wrong_tally"] else None
        )
        questions.append({
            "qi":               qi,
            "question":         s["question"],
            "correct_pct":      round(s["correct"] / s["total"] * 100) if s["total"] > 0 else None,
            "attempt_count":    s["total"],
            "most_wrong_option": most_wrong,
        })

    # Sort hardest first (lowest correct %)
    questions.sort(key=lambda x: x["correct_pct"] if x["correct_pct"] is not None else 100)

    return {
        "concept_id":     concept_id,
        "total_attempts": total_attempts,
        "questions":      questions,
    }


class HeartbeatRequest(BaseModel):
    seconds: int  # seconds spent since last heartbeat (client sends every 30s)


@router.post("/concepts/{concept_id}/heartbeat")
async def concept_heartbeat(concept_id: str, req: HeartbeatRequest, authorization: str = Header(...)):
    """
    Student time-on-page signal — client sends every 30 s while the page is open.
    Accumulates into concept_time_logs (one row per student × concept × day).
    Capped at 3 600 s per call to guard against tab-left-open drift.
    """
    student_id = await _get_student(authorization)
    seconds    = max(1, min(3600, req.seconds))
    async with get_db() as db:
        await db.execute("""
            INSERT INTO concept_time_logs (student_id, concept_id, log_date, seconds_spent)
            VALUES ($1::uuid, $2::uuid, CURRENT_DATE, $3)
            ON CONFLICT (student_id, concept_id, log_date)
            DO UPDATE SET seconds_spent = concept_time_logs.seconds_spent + $3
        """, student_id, concept_id, seconds)
    return {"ok": True}


class VideoProgressRequest(BaseModel):
    pct: float              # 0–100, the watch percentage reached
    block_id: str = 'legacy'  # content-block UUID, or 'legacy' for old single-video concepts


@router.post("/concepts/{concept_id}/video-progress")
async def concept_video_progress(concept_id: str, req: VideoProgressRequest, authorization: str = Header(...)):
    """
    Student video-watch signal — records the highest % watched per content block.
    Tracked per (student, concept, block_id) so multiple videos in one concept are
    counted independently. Only advances pct, never regresses (GREATEST).
    """
    student_id = await _get_student(authorization)
    pct      = max(0.0, min(100.0, req.pct))
    block_id = req.block_id or 'legacy'
    async with get_db() as db:
        await db.execute("""
            INSERT INTO concept_video_watches (student_id, concept_id, block_id, pct_watched, updated_at)
            VALUES ($1::uuid, $2::uuid, $3, $4, NOW())
            ON CONFLICT (student_id, concept_id, block_id)
            DO UPDATE SET
                pct_watched = GREATEST(concept_video_watches.pct_watched, $4),
                updated_at  = NOW()
        """, student_id, concept_id, block_id, pct)
    return {"ok": True}


class FlashcardReviewRequest(BaseModel):
    rating: int  # 1 = again, 4 = got it (same scale as study-set flashcard reviews)


@router.post("/concepts/flashcards/{flashcard_id}/review")
async def review_concept_flashcard(
    flashcard_id: str,
    req: FlashcardReviewRequest,
    authorization: str = Header(...),
):
    """Log a self-rated flashcard review and schedule its next due date (SM-2-style)."""
    from services.srs import next_state, DEFAULT_EASE

    student_id = await _get_student(authorization)
    if req.rating not in (1, 4):
        raise HTTPException(400, "rating must be 1 (again) or 4 (got it)")

    async with get_db() as db:
        card = await db.fetchrow(
            "SELECT id FROM concept_flashcards WHERE id = $1::uuid", flashcard_id
        )
        if not card:
            raise HTTPException(404, "Flashcard not found")

        await db.execute(
            "INSERT INTO concept_flashcard_reviews (student_id, flashcard_id, rating) VALUES ($1::uuid, $2::uuid, $3)",
            student_id, flashcard_id, req.rating,
        )

        state = await db.fetchrow(
            """SELECT repetitions, ease_factor, interval_days
               FROM concept_flashcard_state WHERE student_id = $1::uuid AND flashcard_id = $2::uuid""",
            student_id, flashcard_id,
        )
        repetitions, ease_factor, interval_days = (
            (state["repetitions"], state["ease_factor"], state["interval_days"]) if state
            else (0, DEFAULT_EASE, 0.0)
        )
        repetitions, ease_factor, interval_days, due_at = next_state(
            req.rating, repetitions, ease_factor, interval_days
        )

        await db.execute("""
            INSERT INTO concept_flashcard_state
              (student_id, flashcard_id, repetitions, ease_factor, interval_days, due_at, last_reviewed_at)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, NOW())
            ON CONFLICT (student_id, flashcard_id)
            DO UPDATE SET repetitions = $3, ease_factor = $4, interval_days = $5,
                          due_at = $6, last_reviewed_at = NOW()
        """, student_id, flashcard_id, repetitions, ease_factor, interval_days, due_at)

    return {"ok": True, "due_at": due_at.isoformat(), "interval_days": interval_days}


# ── Chapter upload → AI pipeline ─────────────────────────────────────────────

async def _create_chapter_only(course_id: str, course: dict, file_bytes: bytes, filename: str) -> dict:
    """
    Create the course_chapters row (with the PDF bytes) and an empty unit for it —
    no AI call, no concepts. Concepts are added later either by the teacher
    cropping regions from the PDF or by running _extract_concepts_for_chapter.
    """
    from services.studyset_processor import extract_text_from_pdf

    _, page_count = extract_text_from_pdf(file_bytes)
    chapter_title = filename.replace(".pdf", "")

    async with get_db() as db:
        chapter_row = await db.fetchrow("""
            INSERT INTO course_chapters (course_id, filename, page_count, concept_count, status, pdf_data)
            VALUES ($1::uuid, $2, $3, 0, 'ready', $4) RETURNING id
        """, course_id, filename, page_count, file_bytes)

        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM course_units WHERE course_id = $1::uuid",
            course_id,
        )
        unit_row = await db.fetchrow("""
            INSERT INTO course_units (course_id, title, description, position, chapter_ref)
            VALUES ($1::uuid, $2, $3, $4, $5) RETURNING id
        """, course_id, chapter_title, f"Source: {filename}", int(max_pos) + 1, str(chapter_row["id"]))

    return {
        "chapter_id":    str(chapter_row["id"]),
        "chapter_title": chapter_title,
        "unit_id":       str(unit_row["id"]),
        "concept_count": 0,
        "concept_ids":   [],
        "page_count":    page_count,
    }


async def _extract_concepts_for_chapter(chapter_id: str, unit_id: str, course: dict, file_bytes: bytes, language: str = 'en') -> list[str]:
    """
    AI-extracts concepts with verbatim source chunks from a chapter's full text and
    appends them to an existing unit. Injects per-page markers so the AI can report
    which page each concept starts on (page_start). Falls back to text-search if the
    AI omits page_number. Sets source='ai' on each concept.
    """
    from services.studyset_processor import extract_pages_from_pdf, extract_text_from_pdf, is_sparse_text, extract_text_vision
    from openai import AsyncOpenAI

    pages = extract_pages_from_pdf(file_bytes)

    # Build paged text with markers so AI can report page numbers
    paged_parts = []
    for i, p in enumerate(pages):
        if p.strip():
            paged_parts.append(f"--- Page {i + 1} ---\n{p.strip()}")
    paged_text = "\n\n".join(paged_parts)

    # Scanned PDF fallback: if PyMuPDF returned almost no text, use Claude vision
    # to OCR the pages so concept extraction works on scanned books too.
    if is_sparse_text(paged_text, len(pages)):
        logger.info("[chapter] sparse text (%d chars / %d pages) — switching to vision OCR",
                    len(paged_text), len(pages))
        ocr_text, _ = await extract_text_vision(file_bytes)
        paged_text = ocr_text

    truncated  = paged_text[:80_000]

    concept_lang_note = ""
    if language in _LANGUAGE_NAMES:
        concept_lang_note = f"\nIMPORTANT: Write ALL titles and descriptions in {_LANGUAGE_NAMES[language]}. The source_text must remain verbatim from the document (strip any '--- Page N ---' markers from it)."

    client = AsyncOpenAI()
    _ext_grade = f"\nGrade: {course['grade']}" if course.get("grade") else ""
    _ext_board = f"\nCurriculum Board: {course['board']}" if course.get("board") else ""
    extract_prompt = f"""You are an expert educator. Analyze this chapter and extract the key concepts students must learn.

Course: {course['name']}
Subject: {course['subject'] or 'General'}{_ext_grade}{_ext_board}

The text below is divided by page markers like "--- Page 3 ---". Use these markers to record which page each concept starts on.

STEP 1 — Check for numbered sub-sections.
If the chapter contains numbered headings like "1.1 Title", "1.2 Title", "2.3 Title" etc., create EXACTLY ONE concept per sub-section. Use the sub-section title verbatim as the concept title. Do NOT merge or skip sub-sections.

STEP 2 — Fallback (no numbered structure).
If there are no numbered sub-sections, identify 4–8 distinct learnable ideas in reading order.

For EACH concept, include the EXACT verbatim paragraph(s) from the text it is based on (do NOT include the "--- Page N ---" marker in source_text).

Return ONLY valid JSON:
{{
  "chapter_title": "...",
  "concepts": [
    {{
      "title": "Concise concept name",
      "description": "One sentence: what the student will understand",
      "source_text": "The exact verbatim sentences/paragraphs from the text that cover this concept",
      "page_number": 3
    }}
  ]
}}

Rules:
- Follow numbered sub-section structure when present (this takes priority over the 4–12 range)
- source_text must be a direct quote from the document, without page markers
- page_number is the integer from the nearest "--- Page N ---" marker above this concept's content
- Each concept = one distinct learnable idea{concept_lang_note}

--- CHAPTER ---
{truncated}"""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": extract_prompt}],
        response_format={"type": "json_object"},
        max_tokens=6000,
        temperature=0.2,
    )
    result       = json.loads(response.choices[0].message.content)
    concepts_raw = result.get("concepts", [])

    # Strip any stray page markers the AI may have left in source_text
    _page_marker_re = re.compile(r'---\s*Page\s+\d+\s*---\n?', re.IGNORECASE)

    async with get_db() as db:
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM course_concepts WHERE unit_id = $1::uuid", unit_id
        )
        base_pos = int(max_pos) + 1

        await db.execute(
            "UPDATE course_chapters SET concept_count = concept_count + $1 WHERE id = $2::uuid",
            len(concepts_raw), chapter_id,
        )

        concept_ids = []
        for i, c in enumerate(concepts_raw):
            raw_source = c.get("source_text", "")
            clean_source = _page_marker_re.sub("", raw_source).strip()

            # Option A: AI returned page_number
            page_start: int | None = None
            ai_page = c.get("page_number")
            if isinstance(ai_page, int) and 1 <= ai_page <= len(pages):
                page_start = ai_page

            # Option B fallback: search for the text in the pages list
            if page_start is None and clean_source:
                page_start = _find_page_in_pages(pages, clean_source)

            row = await db.fetchrow("""
                INSERT INTO course_concepts
                  (unit_id, title, description, source_text, pipeline_status, position, chapter_ref, source, page_start)
                VALUES ($1::uuid, $2, $3, $4, 'summarizing', $5, $6, 'ai', $7)
                RETURNING id
            """, unit_id,
                c.get("title", ""), c.get("description", ""),
                clean_source, base_pos + i, chapter_id, page_start)
            concept_ids.append(str(row["id"]))

    return concept_ids


async def _create_chapter_from_pdf(course_id: str, course: dict, file_bytes: bytes, filename: str, language: str = 'en') -> dict:
    """
    Shared by the bulk-split flow: create the chapter+unit, then immediately
    AI-extract concepts for it. Single-chapter upload (upload_chapter below) no
    longer auto-extracts — it calls _create_chapter_only and leaves extraction
    as an opt-in "Suggest concepts" action.
    """
    base = await _create_chapter_only(course_id, course, file_bytes, filename)
    concept_ids = await _extract_concepts_for_chapter(base["chapter_id"], base["unit_id"], course, file_bytes, language)
    base["concept_ids"]   = concept_ids
    base["concept_count"] = len(concept_ids)
    return base


async def _extract_and_summarize_chapter_bg(chapter_id: str, unit_id: str, course: dict, language: str) -> None:
    """Background task: load chapter PDF from DB, extract concepts, then summarize.
    Updates chapter status to 'processing' → 'complete' / 'failed'."""
    try:
        async with get_db() as db:
            row = await db.fetchrow(
                "SELECT pdf_data FROM course_chapters WHERE id = $1::uuid", chapter_id
            )
        if not row or not row["pdf_data"]:
            logger.error("[bulk-split] chapter %s has no PDF data in DB", chapter_id)
            return
        concept_ids = await _extract_concepts_for_chapter(
            chapter_id, unit_id, course, bytes(row["pdf_data"]), language
        )
        async with get_db() as db:
            await db.execute(
                "UPDATE course_chapters SET status = 'complete' WHERE id = $1::uuid", chapter_id
            )
        if concept_ids:
            await _summarize_concepts_bg(concept_ids, str(course["id"]))
    except Exception as exc:
        logger.error("[bulk-split] chapter %s failed: %s", chapter_id, exc)
        async with get_db() as db:
            await db.execute(
                "UPDATE course_chapters SET status = 'failed' WHERE id = $1::uuid", chapter_id
            )


async def _process_chapters_parallel_bg(chapters_info: list[dict], course: dict, language: str) -> None:
    """Background task: extract and summarize all chapters in parallel."""
    import asyncio
    await asyncio.gather(
        *[_extract_and_summarize_chapter_bg(c["chapter_id"], c["unit_id"], course, language)
          for c in chapters_info],
        return_exceptions=True,
    )


@router.post("/{course_id}/chapters")
async def upload_chapter(
    course_id:     str,
    authorization: str        = Header(...),
    file:          UploadFile = File(...),
):
    """Upload a single chapter PDF — lands with an empty unit. Concepts are added
    later by cropping regions from the PDF or via /chapters/{id}/suggest-concepts."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id, name, subject, grade, board FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
    if not course:
        raise HTTPException(404, "Course not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    file_bytes = await file.read()
    if len(file_bytes) > 30 * 1024 * 1024:
        raise HTTPException(400, "File too large — max 30 MB")

    return await _create_chapter_only(course_id, dict(course), file_bytes, file.filename)


@router.post("/chapters/{chapter_id}/suggest-concepts")
async def suggest_concepts(
    chapter_id:    str,
    bg:            BackgroundTasks,
    authorization: str = Header(...),
):
    """Opt-in AI concept extraction for an already-uploaded chapter."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        chapter = await db.fetchrow("""
            SELECT ch.id, ch.pdf_data, ch.course_id, cu.id AS unit_id, c.name, c.subject, c.grade, c.board
            FROM course_chapters ch
            JOIN course_units cu ON cu.chapter_ref = ch.id
            JOIN courses c       ON c.id = ch.course_id AND c.teacher_id = $2::uuid
            WHERE ch.id = $1::uuid
        """, chapter_id, teacher_id)
        suggest_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", teacher_id)
    if not chapter or not chapter["pdf_data"]:
        raise HTTPException(404, "Chapter not found")

    course = {"name": chapter["name"], "subject": chapter["subject"], "grade": chapter["grade"], "board": chapter["board"]}
    concept_ids = await _extract_concepts_for_chapter(
        chapter_id, str(chapter["unit_id"]), course, bytes(chapter["pdf_data"]), suggest_lang or 'en',
    )
    bg.add_task(_summarize_concepts_bg, concept_ids, str(chapter["course_id"]))
    return {"concept_ids": concept_ids, "concept_count": len(concept_ids)}


# ── Magic-wand bulk asset generation ──────────────────────────────────────────

class BulkGenerateRequest(BaseModel):
    types:         list[str]   # "summary" | "quiz" | "flashcard" | "audio" | "video" | "suggest"
    skip_existing: bool = True


async def _bulk_generate_bg(
    concept_ids:     list[str],
    types:           set,
    course_id:       str,
    skip_existing:   bool,
    chapter_ref_id:  str | None,
    unit_id:         str | None,
    suggest_lang:    str,
    course_dict:     dict,
    teacher_id:      str | None = None,
) -> None:
    """Background: run per-concept asset generation for all concepts in a chapter."""
    import asyncio

    # Step 0: suggest missing concepts first so they're included in generation
    if 'suggest' in types and chapter_ref_id and unit_id:
        try:
            async with get_db() as db:
                row = await db.fetchrow(
                    "SELECT pdf_data FROM course_chapters WHERE id = $1::uuid", chapter_ref_id
                )
            if row and row["pdf_data"]:
                # Mark as processing so the pipeline endpoint reports is_processing=True
                # while extraction runs (can take 10-30s — longer than the first poll interval).
                async with get_db() as db:
                    await db.execute(
                        "UPDATE course_chapters SET status='processing' WHERE id=$1",
                        chapter_ref_id,
                    )
                new_ids = await _extract_concepts_for_chapter(
                    chapter_ref_id, unit_id, course_dict, bytes(row["pdf_data"]), suggest_lang
                )
                concept_ids = list(set(list(concept_ids) + new_ids))
                async with get_db() as db:
                    await db.execute(
                        "UPDATE course_chapters SET status=$1 WHERE id=$2",
                        'complete' if new_ids else 'failed', chapter_ref_id,
                    )
        except Exception as exc:
            logger.error("[bulk-gen] suggest failed for chapter %s: %s", chapter_ref_id, exc)
            async with get_db() as db:
                await db.execute(
                    "UPDATE course_chapters SET status='failed' WHERE id=$1", chapter_ref_id
                )

    gen_types = types - {'suggest'}
    if not gen_types or not concept_ids:
        return

    async def _one(concept_id: str) -> None:
        try:
            async with get_db() as db:
                c = await db.fetchrow("""
                    SELECT pipeline_status, ai_summary, ai_transcript,
                           quiz_status, flashcard_status, audio_status, video_status
                    FROM course_concepts WHERE id = $1::uuid
                """, concept_id)
            if not c:
                return

            # --- Summary (must come first — audio/video depend on it) ---
            summary_just_generated = False
            if 'summary' in gen_types and (not skip_existing or not c["ai_summary"]):
                async with get_db() as db:
                    await db.execute(
                        "UPDATE course_concepts SET pipeline_status='summarizing' WHERE id=$1::uuid",
                        concept_id,
                    )
                await _summarize_one_concept(concept_id, course_dict)
                summary_just_generated = True
                async with get_db() as db:
                    c = await db.fetchrow(
                        "SELECT ai_summary, ai_transcript, quiz_status, flashcard_status, audio_status, video_status FROM course_concepts WHERE id=$1::uuid",
                        concept_id,
                    )

            # Inject summary into the concept's authoring chat so the teacher
            # immediately sees a draft when they open the Studio tab.
            # Runs whether summary was just generated or already existed — either way,
            # if there's no chat yet and a summary is available, seed it.
            if 'summary' in gen_types and teacher_id and c and c["ai_summary"]:
                try:
                    async with get_db() as db:
                        existing_conv = await db.fetchrow(
                            "SELECT id FROM conversations WHERE concept_id = $1::uuid", concept_id
                        )
                    if not existing_conv:
                        async with get_db() as db:
                            info = await db.fetchrow("""
                                SELECT cc.title, c.subject
                                FROM course_concepts cc
                                JOIN course_units cu ON cu.id = cc.unit_id
                                JOIN courses c ON c.id = cu.course_id
                                WHERE cc.id = $1::uuid
                            """, concept_id)
                        if info:
                            chat_content = f"### SUMMARY\n{c['ai_summary']}"
                            if c["ai_transcript"]:
                                chat_content += f"\n\n### TRANSCRIPT\n{c['ai_transcript']}"
                            async with get_db() as db:
                                conv = await db.fetchrow("""
                                    INSERT INTO conversations
                                      (user_id, title, subject, concept_id, conversation_type)
                                    VALUES ($1::uuid, $2, $3, $4::uuid, 'studio') RETURNING id
                                """, teacher_id,
                                    f"{info['title']} — Authoring chat",
                                    info["subject"], concept_id)
                                await db.execute(
                                    "INSERT INTO messages (conversation_id, role, content) "
                                    "VALUES ($1::uuid, 'user', $2)",
                                    conv["id"], "Generate a first draft.",
                                )
                                await db.execute(
                                    "INSERT INTO messages (conversation_id, role, content) "
                                    "VALUES ($1::uuid, 'assistant', $2)",
                                    conv["id"], chat_content,
                                )
                except Exception as exc:
                    logger.error("[bulk-gen] chat inject failed for concept %s: %s", concept_id, exc)

            # --- Quiz + Flashcard + Audio in parallel ---
            tier2: list = []
            if 'quiz' in gen_types and (not skip_existing or c["quiz_status"] not in ("ready", "approved", "generating")):
                async with get_db() as db:
                    await db.execute("UPDATE course_concepts SET quiz_status='generating' WHERE id=$1::uuid", concept_id)
                tier2.append(_generate_quiz_bg(concept_id, course_id))

            if 'flashcard' in gen_types and (not skip_existing or c["flashcard_status"] not in ("ready", "approved", "generating")):
                async with get_db() as db:
                    await db.execute("UPDATE course_concepts SET flashcard_status='generating' WHERE id=$1::uuid", concept_id)
                tier2.append(_generate_flashcards_bg(concept_id, course_id))

            if tier2:
                await asyncio.gather(*tier2, return_exceptions=True)

            # --- Video: fire-and-forget (slow, doesn't block the above) ---
            if 'video' in gen_types and (c["ai_transcript"] or c["ai_summary"]) and \
               (not skip_existing or c["video_status"] not in ("ready", "approved", "generating")):
                async with get_db() as db:
                    await db.execute(
                        "UPDATE course_concepts SET video_status='generating', video_error=NULL WHERE id=$1::uuid",
                        concept_id,
                    )
                asyncio.ensure_future(_generate_concept_video_bg(concept_id, course_id, teacher_id))

        except Exception as exc:
            logger.error("[bulk-gen] concept %s failed: %s", concept_id, exc)

    await asyncio.gather(*[_one(cid) for cid in concept_ids], return_exceptions=True)


@router.post("/{course_id}/chapters/{chapter_ref_id}/bulk-generate")
async def bulk_generate_chapter(
    course_id:      str,
    chapter_ref_id: str,
    req:            BulkGenerateRequest,
    bg:             BackgroundTasks,
    authorization:  str = Header(...),
):
    """Teacher magic-wand: queue background generation of selected asset types for all chapter concepts."""
    teacher_id = await _require_teacher(authorization)

    async with get_db() as db:
        chapter = await db.fetchrow("""
            SELECT ch.id, cu.id AS unit_id, c.name, c.subject
            FROM course_chapters ch
            JOIN course_units cu ON cu.chapter_ref = ch.id
            JOIN courses c ON c.id = $1::uuid AND c.teacher_id = $2::uuid
            WHERE ch.id = $3::uuid
        """, course_id, teacher_id, chapter_ref_id)
        suggest_lang = await db.fetchval("SELECT language FROM users WHERE id=$1::uuid", teacher_id)
        rows = await db.fetch("""
            SELECT cc.id FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cu.chapter_ref = $1::uuid
        """, chapter_ref_id)

    if not chapter:
        raise HTTPException(404, "Chapter not found")

    concept_ids = [str(r["id"]) for r in rows]
    types       = set(req.types)
    course_dict = {"name": chapter["name"], "subject": chapter["subject"]}

    if not concept_ids and 'suggest' not in types:
        return {"ok": True, "concept_count": 0}

    bg.add_task(
        _bulk_generate_bg,
        concept_ids,
        types,
        course_id,
        req.skip_existing,
        str(chapter["id"]) if 'suggest' in types else None,
        str(chapter["unit_id"]) if 'suggest' in types else None,
        suggest_lang or 'en',
        course_dict,
        str(teacher_id),
    )

    return {"ok": True, "concept_count": len(concept_ids)}


class RegionConceptRequest(BaseModel):
    unit_id:        str
    image_data_url: str


@router.post("/chapters/{chapter_id}/concepts/from-region")
async def create_concept_from_region(
    chapter_id:    str,
    req:           RegionConceptRequest,
    authorization: str = Header(...),
):
    """
    Teacher crops a region of the chapter PDF (captured as a PNG, not a text
    selection — PDF text layers are unreliable for some of these textbooks).
    Vision-transcribes it to source_text, creates a draft concept, stores the
    crop as the concept's first image, and seeds a chat study set immediately.
    """
    region_teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        chapter = await db.fetchrow(
            "SELECT id, course_id FROM course_chapters WHERE id = $1::uuid", chapter_id
        )
        course = await db.fetchrow(
            "SELECT subject FROM courses WHERE id = $1::uuid", chapter["course_id"] if chapter else None
        )
        region_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", region_teacher_id)
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    region_language = region_lang or 'en'

    try:
        header, b64data = req.image_data_url.split(",", 1)
        image_bytes = base64.b64decode(b64data)
        mime = "image/png" if "image/png" in header else "image/jpeg"
    except Exception:
        raise HTTPException(400, "Invalid image data")

    region_lang_note = ""
    if region_language in _LANGUAGE_NAMES:
        region_lang_note = f"\n\nWrite the title in {_LANGUAGE_NAMES[region_language]}. The source_text must remain verbatim from the image."

    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    vision_prompt = f"""This is a cropped region of a textbook page, selected by a teacher to become one
learning concept. Transcribe the text in this image verbatim (preserve numbers, symbols and
equations exactly as shown). If the image is mostly a diagram/illustration with little or no
text, instead write a one-sentence description of what it shows.

Also suggest a concise 3-6 word title for this as a learning concept.{region_lang_note}

Return ONLY valid JSON: {{"title": "...", "source_text": "..."}}"""

    response = await client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64data}"}},
                {"type": "text",      "text": vision_prompt},
            ],
        }],
        response_format={"type": "json_object"},
    )
    result      = json.loads(response.choices[0].message.content)
    title       = (result.get("title") or "Untitled concept").strip()
    source_text = (result.get("source_text") or "").strip()

    async with get_db() as db:
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM course_concepts WHERE unit_id = $1::uuid", req.unit_id
        )
        concept_row = await db.fetchrow("""
            INSERT INTO course_concepts
              (unit_id, title, source_text, pipeline_status, position, chapter_ref, source)
            VALUES ($1::uuid, $2, $3, 'draft', $4, $5, 'manual')
            RETURNING id
        """, req.unit_id, title, source_text, int(max_pos) + 1, chapter_id)
        concept_id = str(concept_row["id"])

        await db.execute("""
            INSERT INTO concept_images (concept_id, data, mime_type, caption, position)
            VALUES ($1::uuid, $2, $3, 'Source excerpt', 0)
        """, concept_id, image_bytes, mime)

    study_set_id = await _create_seeded_study_set(
        title, course["subject"] if course else None, source_text or title,
    )
    async with get_db() as db:
        await db.execute(
            "UPDATE course_concepts SET study_set_id = $1::uuid WHERE id = $2::uuid",
            study_set_id, concept_id,
        )

    return {"concept_id": concept_id, "study_set_id": study_set_id, "title": title, "source_text": source_text}


@router.post("/chapters/{chapter_id}/coverage-check")
async def check_chapter_coverage(chapter_id: str, authorization: str = Header(...)):
    """
    Manual, on-demand sanity check: does anything from the chapter look like it's
    not covered by any concept yet? Topic-level, not page-accurate — good enough
    to point the teacher at what's left without forcing them to re-read the PDF.
    """
    coverage_teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        chapter = await db.fetchrow(
            "SELECT pdf_data FROM course_chapters WHERE id = $1::uuid", chapter_id
        )
        concepts = await db.fetch(
            "SELECT title, source_text FROM course_concepts WHERE chapter_ref = $1::uuid ORDER BY position",
            chapter_id,
        )
        coverage_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", coverage_teacher_id)
    if not chapter or not chapter["pdf_data"]:
        raise HTTPException(404, "Chapter not found")

    from services.studyset_processor import extract_text_from_pdf
    full_text, _ = extract_text_from_pdf(bytes(chapter["pdf_data"]))

    if not concepts:
        return {"coverage_summary": "No concepts have been created for this chapter yet — nothing is covered."}

    covered = "\n\n".join(f"- {c['title']}: {(c['source_text'] or '')[:500]}" for c in concepts)

    coverage_lang_note = ""
    if (coverage_lang or 'en') in _LANGUAGE_NAMES:
        coverage_lang_note = f"\n\nWrite your answer in {_LANGUAGE_NAMES[coverage_lang]}."

    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    prompt = f"""Here is the full text of a textbook chapter, and a list of concepts a teacher has
already created from it (title + excerpt each).

Identify anything meaningful from the chapter that is NOT yet covered by any of these concepts.
Answer in 2-5 short bullet points naming the missing topic/section. If everything meaningful is
already covered, just answer "Fully covered."{coverage_lang_note}

--- FULL CHAPTER TEXT ---
{full_text[:40_000]}

--- CONCEPTS ALREADY CREATED ---
{covered[:8_000]}"""

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.2,
    )
    return {"coverage_summary": response.choices[0].message.content.strip()}


@router.post("/{course_id}/chapters/detect-toc")
async def detect_chapter_toc(
    course_id:     str,
    authorization: str        = Header(...),
    file:          UploadFile = File(...),
):
    """
    Preview-only: look for a table of contents in an uploaded textbook PDF and
    propose a chapter/page-range split. Makes no DB writes — the teacher reviews
    and edits the result, then POSTs the confirmed list to /chapters/bulk-split.
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchval(
            "SELECT id FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        toc_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", teacher_id)
    if not course:
        raise HTTPException(404, "Course not found")

    toc_language = toc_lang or 'en'

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    file_bytes = await file.read()
    if len(file_bytes) > 30 * 1024 * 1024:
        raise HTTPException(400, "File too large — max 30 MB")

    import fitz
    from services.studyset_processor import extract_pages_from_pdf

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_count = len(doc)
    outline = doc.get_toc()  # [[level, title, page], ...] — 1-indexed page numbers
    doc.close()

    entries: list[dict] = []
    method = "none"
    pages: list[str] | None = None

    top_level = [o for o in outline if o[0] == 1] if outline else []
    # Drop obvious front-matter/back-matter bookmarks (publishers often bookmark
    # a cover, TOC, or Index page) — these aren't real chapters and would
    # otherwise eat the first chapter's pages as their own.
    top_level = [o for o in top_level if not _FRONT_MATTER_RE.search(o[1])]
    if len(top_level) >= 4:
        # Enough level-1 chapters to trust the outline without a cross-check.
        method = "outline"
        entries = [{"title": o[1].strip(), "start_page": int(o[2])} for o in top_level]
    elif outline:
        # Fewer than 4 level-1 chapters — also inspect level-2 in case the real
        # chapters are nested under a structural bookmark (e.g. "Contents").
        level2 = [o for o in outline if o[0] == 2 and not _FRONT_MATTER_RE.search(o[1])]
        best = top_level if len(top_level) >= len(level2) else level2
        if len(best) >= 2:
            method = "outline"
            entries = [{"title": o[1].strip(), "start_page": int(o[2])} for o in best]

    # Vision is the primary fallback: reads actual page images so it handles
    # scanned PDFs, images mid-TOC, decorative fonts, and multi-language books.
    # Run it whenever the outline gave fewer than 4 chapters for a real book.
    if (method == "none" or len(entries) < 4) and page_count > 20:
        vis = await _detect_toc_vision(file_bytes, page_count)
        if len(vis) >= 2 and len(vis) >= len(entries):
            entries = vis
            method = "vision"

    # Last resort: text extraction + GPT (digital PDFs with readable text only).
    if method == "none":
        if pages is None:
            pages = extract_pages_from_pdf(file_bytes)
        text_entries = await _detect_toc_from_text(pages)
        if len(text_entries) >= 2:
            entries = text_entries
            method = "contents_page"

    chapters = []
    for i, e in enumerate(entries):
        start = max(1, e["start_page"])
        if i + 1 < len(entries):
            end = max(start, entries[i + 1]["start_page"] - 1)
            low_confidence = False
        else:
            end = page_count
            low_confidence = True
        chapters.append({
            "title": e["title"], "start_page": start, "end_page": end,
            "low_confidence": low_confidence,
        })

    # Embedded outline labels are often internal filename slugs, or a
    # transliteration in a different script/language than the book's own
    # content (e.g. "Vargangal" for a Malayalam chapter actually titled with
    # Malayalam script on the page) — neither case is reliably detectable from
    # the label text alone, so always cross-check every outline title against
    # that chapter's actual first-page text rather than guessing which ones
    # look "messy".
    if method == "outline" and chapters:
        if pages is None:
            pages = extract_pages_from_pdf(file_bytes)
        await _clean_outline_titles(chapters, list(range(len(chapters))), pages, toc_language)

    return {
        "detected":   len(chapters) >= 2,
        "method":     method,
        "page_count": page_count,
        "chapters":   chapters,
    }


_FRONT_MATTER_RE = re.compile(
    r"front\s*page|cover|preface|title\s*page|^toc$|table of contents|acknowledg"
    r"|^contents?$|^index$|^indices$|bibliography|^references?$|^glossary$|^appendix|^foreword$",
    re.IGNORECASE,
)

_TOC_HEADER_RE = re.compile(
    r"CONTENTS?|SISÄLLYS(LUETTELO)?|INNEHÅLL(SFÖRTECKNING)?|INHALTS?VERZEICHNIS|SOMMAIRE|INDICE",
    re.IGNORECASE,
)


async def _detect_toc_vision(file_bytes: bytes, page_count: int) -> list[dict]:
    """Render the first 15 PDF pages as images and ask Claude Haiku to find the
    Table of Contents and return each chapter's PHYSICAL page position.
    Works on digital PDFs, scanned books, and complex layouts (images mid-TOC)."""
    import fitz, base64
    import anthropic

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    scan_pages = min(15, page_count)
    mat = fitz.Matrix(1.2, 1.2)
    content: list[dict] = []
    for idx in range(scan_pages):
        pix = doc[idx].get_pixmap(matrix=mat)
        b64 = base64.standard_b64encode(pix.tobytes("png")).decode()
        content.append({"type": "text", "text": f"Page {idx + 1}:"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/png", "data": b64,
        }})
    doc.close()

    content.append({"type": "text", "text": (
        f"These are the first {scan_pages} pages of a {page_count}-page textbook PDF.\n\n"
        "1. Find the Table of Contents page.\n"
        "2. List only TOP-LEVEL chapters (ignore sub-sections like 1.1, 1.2, exercises).\n"
        "3. For each chapter, give the PHYSICAL page number where the chapter heading "
        "actually appears in these images. If a chapter starts beyond the pages shown, "
        "calculate its physical page: find which physical page the first chapter starts on, "
        "subtract its printed page number from the TOC, and add that offset to each chapter's "
        "printed page number.\n\n"
        "Return ONLY valid JSON — no prose, no markdown fences:\n"
        "{\"chapters\": [{\"title\": \"...\", \"start_page\": <physical_page_int>}]}"
    )})

    client = anthropic.AsyncAnthropic()
    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": content}],
        )
        raw = re.sub(r'```(?:json)?\s*|\s*```', '', resp.content[0].text)
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            parsed = json.loads(m.group()).get("chapters", [])
            if len(parsed) >= 2:
                return [{"title": c["title"].strip(), "start_page": int(c["start_page"])}
                        for c in parsed]
    except Exception as exc:
        logger.warning("[detect-toc] vision failed: %s", exc)
    return []


async def _detect_toc_from_text(pages: list[str]) -> list[dict]:
    """Scan the first 20 pages for a Contents/TOC page and extract chapters via GPT.
    Returns [{title, start_page}, ...] or [] if nothing useful found.
    Page numbers are calibrated from printed (logical) to physical PDF positions."""
    toc_chunks: list[str] = []
    found_toc_start = False
    toc_start_idx = -1
    toc_end_idx = -1
    for i, p in enumerate(pages[:20]):
        has_keyword = bool(_TOC_HEADER_RE.search(p))
        score = _toc_page_score(p)
        if not found_toc_start:
            if has_keyword or score >= 3:
                found_toc_start = True
                toc_start_idx = i
        # Once TOC is found, collect this page + up to 10 more regardless of
        # score — an embedded image on the TOC page produces score=0 and would
        # otherwise cut the scan short, missing chapters listed after the image.
        if found_toc_start:
            toc_chunks.append(p)
            toc_end_idx = i
            if i >= toc_start_idx + 10:
                break
    if not toc_chunks:
        return []
    contents_page_text = "\n\n".join(toc_chunks)
    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": (
                "Extract the chapter list from this textbook Contents page as JSON. "
                "Ignore sub-sections (e.g. '1.1', '1.2') and exercise labels — only top-level chapters.\n\n"
                "Return ONLY valid JSON: {\"chapters\": [{\"title\": \"...\", \"start_page\": <int>}]}\n\n"
                f"--- CONTENTS ---\n{contents_page_text[:6000]}"
            )}],
            response_format={"type": "json_object"},
            max_tokens=1000,
            temperature=0.0,
        )
        parsed = json.loads(response.choices[0].message.content).get("chapters", [])
        if len(parsed) < 2:
            return []
        entries = [{"title": c["title"].strip(), "start_page": int(c["start_page"])} for c in parsed]
    except Exception as exc:
        logger.warning("[detect-toc] contents-page parse failed: %s", exc)
        return []

    # Calibrate printed page numbers → physical PDF page positions.
    # Textbooks number front-matter separately (roman numerals or skipped),
    # so "Atoms  4" in the TOC means printed page 4 but the actual PDF page
    # is at a different physical position (e.g. physical page 9).
    #
    # Scan the whole PDF for the first chapter's title in the first few lines
    # of each page. A TOC line looks like "Atoms  4" (ends with a page number);
    # an actual chapter heading looks like "Atoms" or "1  Atoms" (no trailing
    # number). We use that distinction to skip TOC/index pages automatically.
    first_title_lower = entries[0]["title"].lower()
    calibrated = False
    for i, p in enumerate(pages):
        if calibrated:
            break
        for line in p.splitlines()[:5]:
            line_lower = line.lower().strip()
            if first_title_lower not in line_lower:
                continue
            # Skip TOC/index lines that end with a standalone page number.
            if re.search(r'\b\d{1,3}\s*$', line_lower):
                continue
            # Found the chapter heading — calculate and apply the offset.
            physical = i + 1  # 1-indexed
            offset = physical - entries[0]["start_page"]
            if offset != 0:
                logger.info("[detect-toc] front-matter offset %+d (printed %d → physical %d)",
                            offset, entries[0]["start_page"], physical)
                entries = [{"title": e["title"], "start_page": max(1, e["start_page"] + offset)}
                           for e in entries]
            calibrated = True
            break

    return entries


def _find_page_in_pages(pages: list[str], snippet: str) -> int | None:
    """Option-B fallback: scan the per-page text list for the first page that contains
    the leading snippet of source_text. Returns 1-indexed page number, or None."""
    query = snippet[:80].strip().lower()
    if not query:
        return None
    for i, p in enumerate(pages):
        if query in p.lower():
            return i + 1
    # Retry with an even shorter anchor in case of minor formatting differences
    short = query[:40]
    for i, p in enumerate(pages):
        if short in p.lower():
            return i + 1
    return None


def _toc_page_score(text: str) -> int:
    """Count lines that have the structural signature of a TOC entry: starts with a
    number (chapter/section), has some text, and ends with a page number.
    Language-agnostic — works for any textbook regardless of the heading word used."""
    count = 0
    for line in text.splitlines():
        line = line.strip()
        if re.match(r'^\d+[\d.]*\s+\S', line) and re.search(r'\b\d{1,3}\s*$', line):
            count += 1
    return count


async def _clean_outline_titles(chapters: list[dict], indices: list[int], pages: list[str], language: str = 'en') -> None:
    """
    Cross-check each outline title against that chapter's actual first-page text,
    replacing it in place with a clean readable title in the teacher's language.
    """
    snippets = []
    for i in indices:
        start_idx = chapters[i]["start_page"] - 1
        text = pages[start_idx][:1200] if 0 <= start_idx < len(pages) else ""
        snippets.append({"index": i, "label": chapters[i]["title"], "page_text": text})

    target_lang = _LANGUAGE_NAMES.get(language, 'English')
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": (
                "Each item below is a chapter label from a PDF's bookmarks, paired with the actual "
                "text from that chapter's first page. The label may be an internal filename slug, or "
                "a transliteration of the book's own (possibly non-English) heading — labels can look "
                "like perfectly normal words and still need fixing for this reason, so always check "
                "against the page text rather than trusting the label's shape.\n\n"
                f"For each item, return a clean, concise chapter title in {target_lang}, derived from the "
                "page text. Even if the label already looks like a real title, verify and translate it "
                f"to {target_lang} if it isn't already.\n\n"
                "Return ONLY valid JSON: {\"titles\": [{\"index\": <int>, \"title\": \"...\"}]}\n\n"
                f"{json.dumps(snippets)[:12000]}"
            )}],
            response_format={"type": "json_object"},
            max_tokens=1000,
            temperature=0.0,
        )
        for item in json.loads(response.choices[0].message.content).get("titles", []):
            idx = item.get("index")
            if isinstance(idx, int) and 0 <= idx < len(chapters) and item.get("title"):
                chapters[idx]["title"] = item["title"].strip()
    except Exception as exc:
        logger.warning("[detect-toc] title cleanup failed, keeping original labels: %s", exc)


class BulkSplitChapter(BaseModel):
    title:      str
    start_page: int
    end_page:   int


@router.post("/{course_id}/chapters/bulk-split")
async def bulk_split_chapters(
    course_id:     str,
    bg:            BackgroundTasks,
    authorization: str        = Header(...),
    file:          UploadFile = File(...),
    chapters:      str        = Form(...),
):
    """
    Slice an uploaded textbook PDF into the teacher-confirmed chapter page ranges
    and run the normal per-chapter pipeline (_create_chapter_from_pdf) once per
    chapter. The file is re-uploaded here (stateless — no server-side temp storage
    needed between /detect-toc and this call).
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id, name, subject, grade, board FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        bulk_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", teacher_id)
    if not course:
        raise HTTPException(404, "Course not found")

    bulk_language = bulk_lang or 'en'

    try:
        chapter_specs = [BulkSplitChapter(**c) for c in json.loads(chapters)]
    except Exception:
        raise HTTPException(400, "Invalid chapters payload")
    if not chapter_specs or len(chapter_specs) > 20:
        raise HTTPException(400, "Provide between 1 and 20 chapters")

    file_bytes = await file.read()
    if len(file_bytes) > 30 * 1024 * 1024:
        raise HTTPException(400, "File too large — max 30 MB")

    import fitz
    source_doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_count = len(source_doc)

    # ── Phase 1: slice PDFs and create DB rows (fast, done before returning) ──
    results      = []
    chapters_info: list[dict] = []
    for spec in chapter_specs:
        if spec.start_page > page_count:
            logger.warning(
                "[bulk-split] skipping '%s': start_page %d > PDF page_count %d",
                spec.title, spec.start_page, page_count,
            )
            results.append({"title": spec.title, "skipped": True, "reason": "start_page beyond PDF length"})
            continue

        start = max(1, min(spec.start_page, page_count))
        end   = max(start, min(spec.end_page, page_count))

        sliced = fitz.open()
        sliced.insert_pdf(source_doc, from_page=start - 1, to_page=end - 1)
        sliced_bytes = sliced.tobytes()
        sliced.close()

        base = await _create_chapter_only(course_id, dict(course), sliced_bytes, f"{spec.title}.pdf")
        chapters_info.append({"chapter_id": base["chapter_id"], "unit_id": base["unit_id"]})
        results.append({"title": spec.title, "chapter_id": base["chapter_id"], "unit_id": base["unit_id"]})

    source_doc.close()

    # Mark all created chapters as 'processing' so the pipeline endpoint
    # reports is_processing=True immediately (before any concepts exist).
    if chapters_info:
        chapter_ids = [c["chapter_id"] for c in chapters_info]
        async with get_db() as db:
            await db.execute(
                "UPDATE course_chapters SET status = 'processing' WHERE id = ANY($1::uuid[])",
                chapter_ids,
            )

    # ── Phase 2: queue parallel extraction as a background task, return now ──
    if chapters_info:
        bg.add_task(_process_chapters_parallel_bg, chapters_info, dict(course), bulk_language)

    return {
        "chapters":      results,
        "chapter_count": len(chapters_info),
        "concept_count": 0,   # filled in as background task runs; frontend polls /pipeline
    }


# ── Pipeline status (teacher polls while concepts are summarizing) ─────────────

@router.get("/{course_id}/pipeline")
async def get_pipeline_status(course_id: str, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        ok = await db.fetchval(
            "SELECT 1 FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
        if not ok:
            raise HTTPException(404, "Course not found")

        rows = await db.fetch("""
            SELECT cc.id, cc.title, cc.pipeline_status, cc.approved_at,
                   cu.title AS unit_title
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid
            ORDER BY cu.position, cc.position
        """, course_id)

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["pipeline_status"]] = counts.get(r["pipeline_status"], 0) + 1

    # Also check whether any chapters are still being processed in the background
    # (concept extraction phase — no concepts exist in DB yet for those chapters).
    async with get_db() as db:
        processing_chapters = await db.fetchval("""
            SELECT COUNT(*) FROM course_chapters ch
            JOIN course_units cu ON cu.chapter_ref = ch.id
            WHERE cu.course_id = $1::uuid AND ch.status = 'processing'
        """, course_id)

    # Sync video_status on any concept whose Cloud Run job has since completed/failed.
    # Cloud Run writes directly to the videos table; this keeps course_concepts in step
    # without requiring a separate webhook, so the pipeline banner clears correctly.
    async with get_db() as db:
        await db.execute("""
            UPDATE course_concepts AS cc
            SET video_status = CASE
                    WHEN v.status IN ('complete', 'completed') THEN 'ready'
                    WHEN v.status = 'failed' THEN 'failed'
                    ELSE cc.video_status
                END,
                video_url = CASE
                    WHEN v.status IN ('complete', 'completed') THEN v.video_url
                    ELSE cc.video_url
                END,
                video_error = CASE
                    WHEN v.status = 'failed' THEN v.error_message
                    ELSE cc.video_error
                END
            FROM videos v, course_units cu
            WHERE cu.course_id = $1::uuid
              AND cc.unit_id = cu.id
              AND cc.video_status = 'generating'
              AND cc.video_job_id = v.id
              AND v.status IN ('complete', 'completed', 'failed')
        """, course_id)

    # Also count concepts with in-flight asset generation (quiz/flashcard/audio/video).
    async with get_db() as db:
        generating_assets = await db.fetchval("""
            SELECT COUNT(*) FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cu.course_id = $1::uuid
              AND (cc.quiz_status = 'generating' OR cc.flashcard_status = 'generating'
                   OR cc.audio_status = 'generating' OR cc.video_status = 'generating')
        """, course_id)

    return {
        "is_processing": (
            counts.get("summarizing", 0) > 0
            or int(processing_chapters or 0) > 0
            or int(generating_assets or 0) > 0
        ),
        "counts":        counts,
        "concepts": [
            {
                "id":              str(r["id"]),
                "title":           r["title"],
                "pipeline_status": r["pipeline_status"],
                "unit_title":      r["unit_title"],
                "approved_at":     r["approved_at"].isoformat() if r["approved_at"] else None,
            }
            for r in rows
        ],
    }


# ── Chapter PDF ───────────────────────────────────────────────────────────────

@router.get("/chapters/{chapter_id}/pdf")
async def get_chapter_pdf(chapter_id: str, authorization: str = Header(...)):
    """Serve the original chapter PDF that was uploaded."""
    await _require_teacher(authorization)
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT pdf_data, filename FROM course_chapters WHERE id = $1::uuid", chapter_id
        )
    if not row or not row["pdf_data"]:
        raise HTTPException(404, "Chapter PDF not found")
    fname = (row["filename"] or "chapter.pdf").replace('"', '')
    return Response(
        content=bytes(row["pdf_data"]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


# ── Syllabus PDF ──────────────────────────────────────────────────────────────

@router.get("/{course_id}/syllabus")
async def get_course_syllabus(course_id: str, authorization: str = Header(...)):
    """Return the stored syllabus PDF for the concept editor."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT syllabus_pdf, syllabus_filename FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
    if not row or not row["syllabus_pdf"]:
        raise HTTPException(404, "No syllabus PDF on file — import a syllabus first")
    fname = (row["syllabus_filename"] or "syllabus.pdf").replace('"', '')
    return Response(
        content=bytes(row["syllabus_pdf"]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )


# ── Concept detail (teacher write, student read) ───────────────────────────────

class ConceptDetailPatch(BaseModel):
    content_text:  str | None = None
    study_set_id:  str | None = None
    ai_summary:    str | None = None
    ai_transcript: str | None = None
    approve:       bool       = False


@router.get("/concepts/{concept_id}/detail")
async def get_concept_detail(concept_id: str, authorization: str = Header(...)):
    """Any authenticated user can fetch concept detail."""
    decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.title, cc.description, cc.content_text,
                   cc.study_set_id, cc.source_text, cc.ai_summary,
                   cc.ai_transcript, cc.pipeline_status, cc.approved_at,
                   cc.quiz_status, cc.flashcard_status, cc.audio_status, cc.video_status,
                   cc.chapter_ref, cc.page_start, cc.suggested_prompts,
                   (cc.audio_data IS NOT NULL) AS has_audio,
                   (cc.video_url IS NOT NULL) AS has_video,
                   cu.course_id
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cc.id = $1::uuid
        """, concept_id)
        if not concept:
            raise HTTPException(404, "Concept not found")

        images = await db.fetch("""
            SELECT id, mime_type, caption, position
            FROM concept_images
            WHERE concept_id = $1::uuid
            ORDER BY position, created_at
        """, concept_id)

        resources = await db.fetch("""
            SELECT id, type, title, mime_type, video_url, position
            FROM concept_resources
            WHERE concept_id = $1::uuid
            ORDER BY position, created_at
        """, concept_id)

    return {
        "id":              str(concept["id"]),
        "title":           concept["title"],
        "description":     concept["description"],
        "content_text":    concept["content_text"],
        "study_set_id":    str(concept["study_set_id"]) if concept["study_set_id"] else None,
        "course_id":       str(concept["course_id"]),
        "source_text":     concept["source_text"],
        "ai_summary":      concept["ai_summary"],
        "ai_transcript":   concept["ai_transcript"],
        "pipeline_status": concept["pipeline_status"],
        "approved_at":      concept["approved_at"].isoformat() if concept["approved_at"] else None,
        "chapter_ref":      concept["chapter_ref"],
        "page_start":       concept["page_start"],
        "quiz_status":      concept["quiz_status"],
        "flashcard_status": concept["flashcard_status"],
        "audio_status":     concept["audio_status"],
        "video_status":     concept["video_status"],
        "has_audio":          bool(concept["has_audio"]),
        "has_video":          bool(concept["has_video"]),
        "audio_url":          f"/api/courses/concepts/{concept_id}/audio" if concept["has_audio"] else None,
        "video_url":          f"/api/courses/concepts/{concept_id}/video" if concept["has_video"] else None,
        "suggested_prompts":  list(concept["suggested_prompts"]) if concept["suggested_prompts"] else [],
        "images": [
            {
                "id":       str(img["id"]),
                "url":      f"/api/courses/concepts/images/{img['id']}",
                "caption":  img["caption"] or "",
                "position": img["position"],
            }
            for img in images
        ],
        "resources": [
            {
                "id":       str(r["id"]),
                "type":     r["type"],
                "title":    r["title"] or "",
                "mime_type": r["mime_type"],
                "video_url": r["video_url"],
                "file_url":  f"/api/courses/concepts/resources/{r['id']}/file" if r["type"] in ("image", "pdf") else None,
                "position":  r["position"],
            }
            for r in resources
        ],
    }


@router.patch("/concepts/{concept_id}/detail")
async def update_concept_detail(
    concept_id: str,
    req: ConceptDetailPatch,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    sets, params = [], [concept_id]
    if req.content_text is not None:
        params.append(req.content_text);  sets.append(f"content_text = ${len(params)}")
    if req.study_set_id is not None:
        params.append(req.study_set_id);  sets.append(f"study_set_id = ${len(params)}::uuid")
    if req.ai_summary is not None:
        params.append(req.ai_summary);    sets.append(f"ai_summary = ${len(params)}")
    if req.ai_transcript is not None:
        params.append(req.ai_transcript); sets.append(f"ai_transcript = ${len(params)}")
    if req.approve:
        sets.append("pipeline_status = 'approved'")
        sets.append("approved_at = NOW()")
    if not sets:
        return {"ok": True}
    async with get_db() as db:
        await db.execute(
            f"UPDATE course_concepts SET {', '.join(sets)} WHERE id = $1::uuid", *params
        )
    return {"ok": True}


async def _create_seeded_study_set(title: str, subject: str | None, material_text: str) -> str:
    """Creates a study_sets row + a ready study_materials row seeded with material_text — no upload step needed."""
    async with get_db() as db:
        study_set = await db.fetchrow("""
            INSERT INTO study_sets (title, subject, description, status)
            VALUES ($1, $2, $3, 'ready')
            RETURNING id
        """, title, subject or "General", f'Auto-created from course material for "{title}"')
        study_set_id = study_set["id"]
        await db.execute("""
            INSERT INTO study_materials (study_set_id, filename, raw_text, char_count, status)
            VALUES ($1::uuid, $2, $3, $4, 'ready')
        """, study_set_id, f"{title}.txt", material_text, len(material_text))
    return str(study_set_id)


@router.post("/concepts/{concept_id}/studyset")
async def create_concept_studyset(concept_id: str, authorization: str = Header(...)):
    """
    Auto-seed a study set for this concept from material we already have — the
    chapter's full extracted text if it came from the chapter-upload pipeline,
    falling back to the concept's own source_text excerpt otherwise. No-op (just
    returns the existing one) if the concept already has a study set linked.
    """
    await _require_teacher(authorization)
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.title, cc.source_text, cc.study_set_id, cc.chapter_ref, c.subject
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")
    if concept["study_set_id"]:
        return {"study_set_id": str(concept["study_set_id"])}

    material_text = concept["source_text"] or concept["title"]
    if concept["chapter_ref"]:
        async with get_db() as db:
            chapter = await db.fetchrow(
                "SELECT pdf_data FROM course_chapters WHERE id = $1::uuid", concept["chapter_ref"]
            )
        if chapter and chapter["pdf_data"]:
            from services.studyset_processor import extract_text_from_pdf
            full_text, _ = extract_text_from_pdf(bytes(chapter["pdf_data"]))
            if full_text:
                material_text = full_text

    study_set_id = await _create_seeded_study_set(concept["title"], concept["subject"], material_text)

    async with get_db() as db:
        await db.execute(
            "UPDATE course_concepts SET study_set_id = $1::uuid WHERE id = $2::uuid",
            study_set_id, concept_id,
        )
    return {"study_set_id": study_set_id}


# ── Concept images ────────────────────────────────────────────────────────────

@router.post("/concepts/{concept_id}/images")
async def upload_concept_image(
    concept_id:    str,
    authorization: str        = Header(...),
    file:          UploadFile = File(...),
    caption:       str        = Form(""),
):
    await _require_teacher(authorization)
    mime = file.content_type or "image/jpeg"
    if not mime.startswith("image/"):
        raise HTTPException(400, "Only image files are supported")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Image too large — max 10 MB")

    async with get_db() as db:
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM concept_images WHERE concept_id = $1::uuid",
            concept_id,
        )
        row = await db.fetchrow("""
            INSERT INTO concept_images (concept_id, data, mime_type, caption, position)
            VALUES ($1::uuid, $2, $3, $4, $5)
            RETURNING id, caption, position
        """, concept_id, data, mime, caption, int(max_pos) + 1)

    return {
        "id":       str(row["id"]),
        "url":      f"/api/courses/concepts/images/{row['id']}",
        "caption":  row["caption"] or "",
        "position": row["position"],
    }


class ImagePatch(BaseModel):
    caption: str


@router.patch("/concepts/{concept_id}/images/{image_id}")
async def update_concept_image(
    concept_id: str,
    image_id:   str,
    req:        ImagePatch,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "UPDATE concept_images SET caption = $1 WHERE id = $2::uuid AND concept_id = $3::uuid",
            req.caption, image_id, concept_id,
        )
    return {"ok": True}


@router.delete("/concepts/{concept_id}/images/{image_id}")
async def delete_concept_image(
    concept_id: str,
    image_id:   str,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "DELETE FROM concept_images WHERE id = $1::uuid AND concept_id = $2::uuid",
            image_id, concept_id,
        )
    return {"ok": True}


@router.get("/concepts/images/{image_id}")
async def serve_concept_image(image_id: str):
    """Serve a concept image — no auth needed (UUID is unguessable)."""
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT data, mime_type FROM concept_images WHERE id = $1::uuid", image_id
        )
    if not row:
        raise HTTPException(404, "Image not found")
    return Response(
        content=bytes(row["data"]),
        media_type=row["mime_type"],
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/concepts/{concept_id}/resources")
async def list_concept_resources(concept_id: str, authorization: str = Header(...)):
    """Teacher: list supplementary resources for a concept."""
    await _require_teacher(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, type, title, mime_type, video_url, position,
                   (raw_text IS NOT NULL AND length(trim(raw_text)) > 10) AS text_extracted
            FROM concept_resources
            WHERE concept_id = $1::uuid
            ORDER BY position, created_at
        """, concept_id)
    return [
        {
            "id":            str(r["id"]),
            "type":          r["type"],
            "title":         r["title"] or "",
            "mime_type":     r["mime_type"],
            "video_url":     r["video_url"],
            "file_url":      f"/api/courses/concepts/resources/{r['id']}/file" if r["type"] in ("image", "pdf") else None,
            "position":      r["position"],
            "text_extracted": bool(r["text_extracted"]),
        }
        for r in rows
    ]


@router.post("/concepts/{concept_id}/resources")
async def add_concept_resource(
    concept_id: str,
    authorization: str = Header(...),
    resource_type: str = Form(None, alias="type"),
    title: str = Form(""),
    video_url: str = Form(None),
    file: UploadFile = File(None),
):
    """
    Teacher: upload a supplementary image or PDF, or add a video URL.
    For PDFs, text is extracted and stored for student chat grounding.
    """
    await _require_teacher(authorization)
    async with get_db() as db:
        exists = await db.fetchval("SELECT 1 FROM course_concepts WHERE id = $1::uuid", concept_id)
    if not exists:
        raise HTTPException(404, "Concept not found")

    if resource_type == "video":
        if not video_url:
            raise HTTPException(400, "video_url required for video type")
        async with get_db() as db:
            max_pos = await db.fetchval(
                "SELECT COALESCE(MAX(position), -1) FROM concept_resources WHERE concept_id = $1::uuid", concept_id
            )
            row = await db.fetchrow("""
                INSERT INTO concept_resources (concept_id, type, title, video_url, position)
                VALUES ($1::uuid, 'video', $2, $3, $4)
                RETURNING id, position
            """, concept_id, title or "Video", video_url, int(max_pos) + 1)
        return {"id": str(row["id"]), "type": "video", "title": title or "Video",
                "video_url": video_url, "file_url": None, "position": row["position"]}

    if not file:
        raise HTTPException(400, "file required for image or pdf type")

    data     = await file.read()
    mime     = file.content_type or "application/octet-stream"
    raw_text = None

    if mime.startswith("image/"):
        rtype = "image"
    elif mime == "application/pdf" or (file.filename or "").lower().endswith(".pdf"):
        rtype = "pdf"
        mime  = "application/pdf"
        from services.studyset_processor import extract_text_from_pdf
        extracted, _ = extract_text_from_pdf(data)
        # Store NULL when text is empty (scanned/image PDF) so the chat
        # endpoint knows to fall back to vision rendering instead.
        raw_text = extracted.strip() or None
    else:
        raise HTTPException(400, "Unsupported file type — upload an image or PDF")

    async with get_db() as db:
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM concept_resources WHERE concept_id = $1::uuid", concept_id
        )
        row = await db.fetchrow("""
            INSERT INTO concept_resources (concept_id, type, title, file_data, mime_type, raw_text, position)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
            RETURNING id, position
        """, concept_id, rtype, title or file.filename or rtype, data, mime, raw_text, int(max_pos) + 1)

    resource_id = str(row["id"])

    # Immediately sync to study_materials if the concept already has a study set
    if rtype == "pdf" and raw_text:
        async with get_db() as db:
            ss_id = await db.fetchval("SELECT study_set_id FROM course_concepts WHERE id = $1::uuid", concept_id)
        if ss_id:
            async with get_db() as db:
                await db.execute("""
                    INSERT INTO study_materials (study_set_id, filename, raw_text, char_count, status)
                    VALUES ($1::uuid, $2, $3, $4, 'ready')
                    ON CONFLICT DO NOTHING
                """, ss_id, f"resource:{resource_id}", raw_text, len(raw_text))

    return {
        "id":             resource_id,
        "type":           rtype,
        "title":          title or file.filename or rtype,
        "mime_type":      mime,
        "text_extracted": bool(raw_text),  # False = scanned PDF, will use vision fallback
        "video_url": None,
        "file_url":  f"/api/courses/concepts/resources/{resource_id}/file",
        "position":  row["position"],
    }


@router.delete("/concepts/{concept_id}/resources/{resource_id}")
async def delete_concept_resource(concept_id: str, resource_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "DELETE FROM concept_resources WHERE id = $1::uuid AND concept_id = $2::uuid",
            resource_id, concept_id,
        )
    return {"ok": True}


@router.get("/concepts/resources/{resource_id}/file")
async def serve_concept_resource_file(resource_id: str):
    """Serve a concept resource binary (image or PDF). No auth — UUID is unguessable."""
    from fastapi.responses import Response
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT file_data, mime_type FROM concept_resources WHERE id = $1::uuid", resource_id
        )
    if not row or not row["file_data"]:
        raise HTTPException(404, "Resource not found")
    return Response(
        content=bytes(row["file_data"]),
        media_type=row["mime_type"] or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=86400"},
    )


class StudentChatRequest(BaseModel):
    message:         str
    resource_id:     str | None = None  # concept_resources.id to ground/visualise
    conversation_id: str | None = None
    language:        str = 'en'


@router.get("/concepts/{concept_id}/student-chat")
async def get_student_chat(concept_id: str, authorization: str = Header(...)):
    """Return the student's conversation history for this concept."""
    student_id = await _get_student(authorization)
    async with get_db() as db:
        ss_id = await db.fetchval(
            "SELECT study_set_id FROM course_concepts WHERE id = $1::uuid", concept_id
        )
        if not ss_id:
            return []
        conv = await db.fetchrow("""
            SELECT id FROM conversations
            WHERE study_set_id = $1::uuid AND user_id = $2::uuid
            ORDER BY created_at ASC LIMIT 1
        """, ss_id, student_id)
        if not conv:
            return []
        rows = await db.fetch("""
            SELECT id, role, content, created_at
            FROM messages WHERE conversation_id = $1::uuid
            ORDER BY created_at ASC LIMIT 60
        """, conv["id"])
    return [
        {"id": str(r["id"]), "role": r["role"], "content": r["content"],
         "created_at": r["created_at"].isoformat()}
        for r in rows
    ]


@router.post("/concepts/{concept_id}/student-chat")
async def post_student_chat(
    concept_id: str, req: StudentChatRequest, authorization: str = Header(...)
):
    """
    Student Q&A chat grounded in the concept's source text + PDF resources.
    When resource_id points to an image resource the image bytes are sent as
    base64 inline vision content so the AI can actually see the diagram.
    When resource_id points to a PDF its raw_text is surfaced prominently in
    the grounding context for that turn.
    """
    import base64
    from openai import AsyncOpenAI

    student_id = await _get_student(authorization)

    # ── 1. Load concept + auto-create study set ───────────────────────────────
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.title, cc.source_text, cc.study_set_id,
                   cc.chapter_ref, c.subject, c.id as course_id
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id  = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")

    study_set_id = concept["study_set_id"]
    if not study_set_id:
        material_text = concept["source_text"] or concept["title"]
        if concept["chapter_ref"]:
            async with get_db() as db:
                ch = await db.fetchrow(
                    "SELECT pdf_data FROM course_chapters WHERE id = $1::uuid", concept["chapter_ref"]
                )
            if ch and ch["pdf_data"]:
                from services.studyset_processor import extract_text_from_pdf
                full, _ = extract_text_from_pdf(bytes(ch["pdf_data"]))
                if full:
                    material_text = full
        study_set_id = await _create_seeded_study_set(concept["title"], concept["subject"], material_text)
        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET study_set_id = $1::uuid WHERE id = $2::uuid",
                study_set_id, concept_id,
            )

    # ── 2. Load PDF resources with extractable text for grounding ────────────
    async with get_db() as db:
        pdf_resources = await db.fetch("""
            SELECT id, title, raw_text FROM concept_resources
            WHERE concept_id = $1::uuid AND type = 'pdf'
              AND raw_text IS NOT NULL AND length(trim(raw_text)) > 10
        """, concept_id)

    # ── 3. Resolve the referenced resource (image or PDF) ────────────────────
    resource_row    = None
    image_b64_url   = None   # single inline image (concept_image or image resource)
    focused_pdf     = None   # PDF resource with extractable text
    pdf_page_images = []     # rendered pages for image-based PDFs (no text layer)

    if req.resource_id:
        async with get_db() as db:
            resource_row = await db.fetchrow("""
                SELECT id, type, title, file_data, mime_type, raw_text
                FROM concept_resources WHERE id = $1::uuid AND concept_id = $2::uuid
            """, req.resource_id, concept_id)

        if resource_row:
            if resource_row["type"] == "image" and resource_row["file_data"]:
                mime   = resource_row["mime_type"] or "image/jpeg"
                b64    = base64.b64encode(bytes(resource_row["file_data"])).decode()
                image_b64_url = f"data:{mime};base64,{b64}"
            elif resource_row["type"] == "pdf" and resource_row["file_data"]:
                if resource_row["raw_text"] and len(resource_row["raw_text"].strip()) > 10:
                    # Text-based PDF — use raw_text as grounding
                    focused_pdf = resource_row
                else:
                    # Scanned/image PDF — render pages as vision content
                    import fitz
                    doc = fitz.open(stream=bytes(resource_row["file_data"]), filetype="pdf")
                    for i, page in enumerate(doc):
                        if i >= 4:  # max 4 pages
                            break
                        pix  = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        b64  = base64.b64encode(pix.tobytes("png")).decode()
                        pdf_page_images.append(f"data:image/png;base64,{b64}")
                    doc.close()

    # ── 4. Get or create conversation (keyed by study_set + student) ──────────
    conv_id = req.conversation_id
    if not conv_id:
        async with get_db() as db:
            existing = await db.fetchrow("""
                SELECT id FROM conversations
                WHERE study_set_id = $1::uuid AND user_id = $2::uuid
                ORDER BY created_at ASC LIMIT 1
            """, study_set_id, student_id)
        if existing:
            conv_id = str(existing["id"])
        else:
            async with get_db() as db:
                conv = await db.fetchrow("""
                    INSERT INTO conversations (user_id, title, study_set_id)
                    VALUES ($1::uuid, $2, $3::uuid) RETURNING id
                """, student_id, f"{concept['title']} — Q&A", study_set_id)
            conv_id = str(conv["id"])

    # ── 5. Load recent history ────────────────────────────────────────────────
    async with get_db() as db:
        history = list(reversed(await db.fetch("""
            SELECT role, content FROM messages
            WHERE conversation_id = $1::uuid
            ORDER BY created_at DESC LIMIT 8
        """, conv_id)))

    # ── 6. Build system prompt ────────────────────────────────────────────────
    grounding_parts = []
    if concept["source_text"]:
        grounding_parts.append(f"## Concept notes\n{concept['source_text']}")
    for pr in pdf_resources:
        if focused_pdf and str(pr["id"]) == str(focused_pdf["id"]):
            continue  # will be added first, prominently
        grounding_parts.append(f"## Supplementary PDF: {pr['title']}\n{pr['raw_text']}")
    if focused_pdf:
        grounding_parts.insert(0, f"## Focus document: {focused_pdf['title']}\n{focused_pdf['raw_text']}")

    grounding = "\n\n".join(grounding_parts) or concept["title"]

    lang_note = ""
    if req.language in _LANGUAGE_NAMES:
        lang_name = _LANGUAGE_NAMES[req.language]
        lang_note = f"\n\nRespond entirely in {lang_name}."

    # Fetch curriculum context first — it determines the entire prompt structure
    curriculum = None
    if concept.get("course_id"):
        from services.curriculum import get_curriculum_context, build_curriculum_block, get_teks_descriptions
        curriculum = await get_curriculum_context(str(concept["course_id"]))

    if curriculum:
        # Inquiry-first: pedagogy rules lead the prompt; grounding follows as reference only.
        grade = curriculum.get("grade_level", "6th grade")
        system_prompt = (
            f"You are an inquiry-based science tutor for a {grade} classroom. "
            f"Students discover science principles through hands-on experiments and discussion — NOT through direct instruction.\n\n"
            f"CRITICAL INSTRUCTION — INQUIRY PEDAGOGY:\n"
            f"NEVER directly explain scientific concepts or state key ideas as facts. "
            f"When a student asks a factual question, respond with a guiding question that helps them reason it out. "
            f"Examples of good responses:\n"
            f"  • \"What did you notice when you tried that in your experiment?\"\n"
            f"  • \"Why do you think one cup kept things colder than the other?\"\n"
            f"  • \"What do you think causes that to happen?\"\n"
            f"  • \"How does that connect to what you observed in class?\"\n"
            f"Use unit vocabulary naturally in your questions. Guide students toward the ideas — never lecture or give away the answer.\n"
        )
        _teks_descs = await get_teks_descriptions(curriculum.get("teks_codes") or [])
        system_prompt += build_curriculum_block(curriculum, _teks_descs)
        system_prompt += f"\n\n--- LESSON CONTENT (background context — do not recite as answers) ---\n{grounding[:8000]}"
        if lang_note:
            system_prompt += lang_note
    else:
        system_prompt = (
            f"You are a helpful AI tutor helping a student understand \"{concept['title']}\" "
            f"({concept['subject'] or 'General'}).\n\n"
            f"Answer primarily from the material below. If a topic isn't covered, say so briefly "
            f"and answer from your general knowledge where safe to do so.\n\n"
            f"{grounding[:12000]}{lang_note}"
        )

    if image_b64_url:
        system_prompt += (
            "\n\nThe student has shared an image from the concept material. "
            "Describe what you see in it and explain how it relates to the concept."
        )
    if pdf_page_images:
        system_prompt += (
            f"\n\nThe student is asking about a PDF document '{resource_row['title']}'. "
            "The page images are attached below. Read them carefully and answer the student's question."
        )

    # ── 7. Save user message ──────────────────────────────────────────────────
    async with get_db() as db:
        await db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES ($1::uuid, 'user', $2)",
            conv_id, req.message,
        )

    # ── 8. Build AI messages ──────────────────────────────────────────────────
    ai_messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        ai_messages.append({"role": h["role"], "content": h["content"]})

    user_content: list | str
    if image_b64_url or pdf_page_images:
        user_content = [{"type": "text", "text": req.message}]
        if image_b64_url:
            user_content.append({"type": "image_url", "image_url": {"url": image_b64_url, "detail": "high"}})
        for page_url in pdf_page_images:
            user_content.append({"type": "image_url", "image_url": {"url": page_url, "detail": "high"}})
    else:
        user_content = req.message
    ai_messages.append({"role": "user", "content": user_content})

    # ── 9. Call AI ────────────────────────────────────────────────────────────
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=ai_messages,
        max_tokens=1200,
        temperature=0.3,
    )
    reply = response.choices[0].message.content

    # ── 10. Save reply ────────────────────────────────────────────────────────
    async with get_db() as db:
        await db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES ($1::uuid, 'assistant', $2)",
            conv_id, reply,
        )

    return {"reply": reply, "conversation_id": conv_id}


@router.get("/concepts/{concept_id}/video")
async def serve_concept_video(concept_id: str):
    """
    Redirect to the rendered video's R2/Cloudflare URL — no auth (UUID is unguessable).
    The video itself is rendered by the Manim Cloud Run pipeline and stored in R2,
    not in Postgres, so the browser is sent straight to the CDN URL.
    """
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT video_url FROM course_concepts WHERE id = $1::uuid AND video_status IN ('ready','approved')",
            concept_id,
        )
    if not row or not row["video_url"]:
        raise HTTPException(404, "Video not available")
    return RedirectResponse(row["video_url"])


# ── Asset generation backgrounds ─────────────────────────────────────────────

def _shuffle_quiz_options(questions: list) -> list:
    """Randomly redistribute each question's options so the correct answer isn't always first."""
    import random
    out = []
    for q in questions:
        opts = list(q.get("options", []))
        ci   = q.get("correct_idx", 0)
        if opts and 0 <= ci < len(opts):
            answer = opts[ci]
            random.shuffle(opts)
            ci = opts.index(answer)
        out.append({**q, "options": opts, "correct_idx": ci})
    return out


def build_quiz_prompt(title: str, subject: str, source: str, extra: str = "", language: str = 'en', grade: str = "", board: str = "") -> str:
    """Shared by the per-concept quiz generator and the per-student assignment generator."""
    lang_instruction = ""
    if language in _LANGUAGE_NAMES:
        lang_name = _LANGUAGE_NAMES[language]
        lang_instruction = f"\nIMPORTANT: Generate ALL questions, answer options, and explanations in {lang_name}. Do not use English."
    grade_line = f"\nGrade: {grade}" if grade else ""
    board_line = f"\nCurriculum Board: {board}" if board else ""
    return f"""You are an expert educator. Create 6 multiple-choice quiz questions to test student understanding.

Concept: {title}
Subject: {subject}{grade_line}{board_line}
{extra}
Source material:
---
{source[:6000]}
---

Rules:
- Each question must be answerable from the source material
- All 4 options must be plausible (avoid obviously wrong distractors)
- Include a 1-2 sentence explanation for the correct answer
- Vary difficulty: 2 recall, 2 comprehension, 2 application questions{lang_instruction}

Return ONLY valid JSON:
{{"questions": [{{"question": "...", "options": ["A", "B", "C", "D"], "correct_idx": 2, "explanation": "..."}}]}}"""


def build_flashcard_prompt(title: str, source: str, extra: str = "", language: str = 'en') -> str:
    """Shared by the per-concept flashcard generator and the per-student assignment generator."""
    lang_instruction = ""
    if language in _LANGUAGE_NAMES:
        lang_name = _LANGUAGE_NAMES[language]
        lang_instruction = f"\nIMPORTANT: Generate ALL flashcard fronts and backs in {lang_name}. Do not use English."
    return f"""You are an expert educator. Create 10 flashcards to help students memorise key terms and ideas.

Concept: {title}
{extra}
Source material:
---
{source[:6000]}
---

Rules:
- Front: term, definition prompt, or short question (max 12 words)
- Back: precise answer or definition (1-2 sentences)
- Cover key vocabulary, key facts, and cause-effect relationships
- Keep language student-friendly{lang_instruction}

Return ONLY valid JSON:
{{"flashcards": [{{"front": "...", "back": "..."}}]}}"""


def build_quiz_prompt_studio(
    title: str, subject: str, source: str,
    difficulty: str = 'mixed', style: str = 'multiple_choice', count: int = 5,
    language: str = 'en', grade: str = "", board: str = "",
) -> str:
    difficulty_instruction = {
        'easy':  'All questions should be straightforward recall or simple comprehension.',
        'medium':'Mix recall and comprehension questions.',
        'hard':  'Questions should require analysis, application, or synthesis — no simple recall.',
        'mixed': 'Vary difficulty: ~1/3 easy recall, ~1/3 comprehension, ~1/3 application. Add a "difficulty" field ("easy"|"medium"|"hard") to each question.',
    }.get(difficulty, 'Vary difficulty.')
    style_instruction = {
        'multiple_choice': f'Create {count} multiple-choice questions with 4 options each.',
        'true_false':      f'Create {count} true/false questions (2 options: True, False).',
        'mixed':           f'Create {count} questions mixing multiple-choice and true/false.',
    }.get(style, f'Create {count} multiple-choice questions.')
    lang_note = ''
    if language in _LANGUAGE_NAMES:
        lang_note = f'\nIMPORTANT: Generate ALL content in {_LANGUAGE_NAMES[language]}. Do not use English.'
    diff_field = ', "difficulty": "easy|medium|hard"' if difficulty == 'mixed' else ''
    _sq_grade = f"\nGrade: {grade}" if grade else ""
    _sq_board = f"\nCurriculum Board: {board}" if board else ""
    return f"""You are an expert educator. {style_instruction}

Concept: {title}
Subject: {subject}{_sq_grade}{_sq_board}
{difficulty_instruction}

Source material:
---
{source[:8000]}
---

Rules:
- Questions must be answerable from the source material
- All options must be plausible (no obviously wrong distractors)
- Include a 1–2 sentence explanation for the correct answer{lang_note}

Return ONLY valid JSON:
{{"questions": [{{"question": "...", "options": ["A","B","C","D"], "correct_idx": 0, "explanation": "..."{diff_field}}}]}}"""


def build_flashcard_prompt_studio(
    title: str, source: str, count: int = 10, focus: str = 'mixed', language: str = 'en',
) -> str:
    focus_instruction = {
        'definitions': 'Focus on key terms and their definitions.',
        'examples':    'Focus on worked examples and how concepts apply in practice.',
        'mixed':       'Cover key terms, definitions, worked examples, and cause-effect relationships.',
    }.get(focus, 'Cover key vocabulary and key facts.')
    lang_note = ''
    if language in _LANGUAGE_NAMES:
        lang_note = f'\nIMPORTANT: Generate ALL content in {_LANGUAGE_NAMES[language]}.'
    return f"""You are an expert educator. Create exactly {count} flashcards.

Concept: {title}
{focus_instruction}

Source material:
---
{source[:8000]}
---

Rules:
- Front: term, definition prompt, or short question (max 12 words)
- Back: precise answer or definition (1–2 sentences){lang_note}

Return ONLY valid JSON:
{{"flashcards": [{{"front": "...", "back": "..."}}]}}"""


class StudioQuizRequest(BaseModel):
    difficulty: str = 'mixed'
    style:      str = 'multiple_choice'
    count:      int = 5
    image_data_urls: list[str] | None = None


class StudioFlashcardRequest(BaseModel):
    count: int  = 10
    focus: str  = 'mixed'
    image_data_urls: list[str] | None = None


@router.post("/concepts/{concept_id}/concept-chat/generate-quiz")
async def generate_quiz_from_chat(
    concept_id:    str,
    req:           StudioQuizRequest,
    authorization: str = Header(...),
):
    """Studio-driven quiz generation — inserts as drafts, stores a chat confirmation."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.title, cc.source_text, cc.ai_summary, cc.chapter_ref, c.subject, c.grade, c.board
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id  = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
        teacher_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", teacher_id)
    if not concept:
        raise HTTPException(404, "Concept not found")

    language = teacher_lang or 'en'
    source   = concept["source_text"] or concept["ai_summary"] or concept["title"]
    prompt   = build_quiz_prompt_studio(
        concept["title"], concept["subject"] or "General", source,
        difficulty=req.difficulty, style=req.style, count=req.count, language=language,
        grade=concept.get("grade") or "", board=concept.get("board") or "",
    )

    from openai import AsyncOpenAI
    import json as _json
    client = AsyncOpenAI()
    user_content: object = prompt
    if req.image_data_urls:
        user_content = [
            *[{"type": "image_url", "image_url": {"url": u}} for u in req.image_data_urls],
            {"type": "text", "text": prompt},
        ]
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": user_content}],
        response_format={"type": "json_object"},
        max_tokens=3000,
        temperature=0.3,
    )
    questions = _shuffle_quiz_options(_json.loads(response.choices[0].message.content).get("questions", []))

    async with get_db() as db:
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM concept_quiz_questions WHERE concept_id = $1::uuid",
            concept_id,
        )
        for i, q in enumerate(questions):
            diff = q.get("difficulty") or (req.difficulty if req.difficulty != "mixed" else "medium")
            await db.execute("""
                INSERT INTO concept_quiz_questions
                  (concept_id, question, options, correct_idx, explanation, position, status, difficulty)
                VALUES ($1::uuid, $2, $3::jsonb, $4, $5, $6, 'draft', $7)
            """, concept_id, q["question"], _json.dumps(q["options"]),
                q["correct_idx"], q.get("explanation", ""), int(max_pos) + 1 + i, diff)
        await db.execute(
            "UPDATE course_concepts SET quiz_status = 'ready' WHERE id = $1::uuid", concept_id
        )
        conv = await db.fetchrow("SELECT id FROM conversations WHERE concept_id = $1::uuid", concept_id)
        if not conv:
            conv = await db.fetchrow("""
                INSERT INTO conversations (user_id, title, subject, concept_id, conversation_type)
                VALUES ($1::uuid, $2, $3, $4::uuid, 'studio') RETURNING id
            """, teacher_id, f"{concept['title']} — Authoring chat", concept["subject"], concept_id)
        msg = await db.fetchrow("""
            INSERT INTO messages (conversation_id, role, content, metadata)
            VALUES ($1::uuid, 'assistant', $2, $3::jsonb)
            RETURNING id, role, content, created_at
        """, conv["id"],
            f"Generated {len(questions)} quiz questions — review and approve them in the Assets tab.",
            _json.dumps({"content_type": "quiz_draft", "count": len(questions)}))

    return {
        "id":         str(msg["id"]),
        "role":       msg["role"],
        "content":    msg["content"],
        "created_at": msg["created_at"].isoformat(),
        "quizDraft":  True,
        "quizCount":  len(questions),
    }


@router.post("/concepts/{concept_id}/concept-chat/generate-flashcards")
async def generate_flashcards_from_chat(
    concept_id:    str,
    req:           StudioFlashcardRequest,
    authorization: str = Header(...),
):
    """Studio-driven flashcard generation — inserts as drafts, stores a chat confirmation."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.title, cc.source_text, cc.ai_summary, c.subject
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id  = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
        teacher_lang = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", teacher_id)
    if not concept:
        raise HTTPException(404, "Concept not found")

    language = teacher_lang or 'en'
    source   = concept["source_text"] or concept["ai_summary"] or concept["title"]
    prompt   = build_flashcard_prompt_studio(
        concept["title"], source, count=req.count, focus=req.focus, language=language,
    )

    from openai import AsyncOpenAI
    import json as _json
    client = AsyncOpenAI()
    user_content: object = prompt
    if req.image_data_urls:
        user_content = [
            *[{"type": "image_url", "image_url": {"url": u}} for u in req.image_data_urls],
            {"type": "text", "text": prompt},
        ]
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": user_content}],
        response_format={"type": "json_object"},
        max_tokens=2500,
        temperature=0.3,
    )
    cards = _json.loads(response.choices[0].message.content).get("flashcards", [])

    async with get_db() as db:
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM concept_flashcards WHERE concept_id = $1::uuid",
            concept_id,
        )
        for i, card in enumerate(cards):
            await db.execute("""
                INSERT INTO concept_flashcards (concept_id, front, back, position, status)
                VALUES ($1::uuid, $2, $3, $4, 'draft')
            """, concept_id, card["front"], card["back"], int(max_pos) + 1 + i)
        await db.execute(
            "UPDATE course_concepts SET flashcard_status = 'ready' WHERE id = $1::uuid", concept_id
        )
        conv = await db.fetchrow("SELECT id FROM conversations WHERE concept_id = $1::uuid", concept_id)
        if not conv:
            conv = await db.fetchrow("""
                INSERT INTO conversations (user_id, title, subject, concept_id, conversation_type)
                VALUES ($1::uuid, $2, $3, $4::uuid, 'studio') RETURNING id
            """, teacher_id, f"{concept['title']} — Authoring chat", concept["subject"], concept_id)
        msg = await db.fetchrow("""
            INSERT INTO messages (conversation_id, role, content, metadata)
            VALUES ($1::uuid, 'assistant', $2, $3::jsonb)
            RETURNING id, role, content, created_at
        """, conv["id"],
            f"Generated {len(cards)} flashcards — review and approve them in the Assets tab.",
            _json.dumps({"content_type": "flashcard_draft", "count": len(cards)}))

    return {
        "id":              str(msg["id"]),
        "role":            msg["role"],
        "content":         msg["content"],
        "created_at":      msg["created_at"].isoformat(),
        "flashcardDraft":  True,
        "flashcardCount":  len(cards),
    }


# ── Quiz/flashcard per-item management ────────────────────────────────────────

class UpdateQuizQuestionRequest(BaseModel):
    status:     str | None = None
    difficulty: str | None = None
    position:   int | None = None


@router.patch("/concepts/{concept_id}/quiz/{question_id}")
async def update_quiz_question(
    concept_id: str, question_id: str,
    req: UpdateQuizQuestionRequest,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    sets, vals = [], []
    if req.status     is not None: sets.append(f"status = ${len(vals)+1}");     vals.append(req.status)
    if req.difficulty is not None: sets.append(f"difficulty = ${len(vals)+1}"); vals.append(req.difficulty)
    if req.position   is not None: sets.append(f"position = ${len(vals)+1}");   vals.append(req.position)
    if not sets:
        return {"ok": True}
    async with get_db() as db:
        await db.execute(
            f"UPDATE concept_quiz_questions SET {', '.join(sets)} WHERE id = ${len(vals)+1}::uuid AND concept_id = ${len(vals)+2}::uuid",
            *vals, question_id, concept_id,
        )
    return {"ok": True}


@router.delete("/concepts/{concept_id}/quiz/{question_id}")
async def delete_quiz_question(
    concept_id: str, question_id: str, authorization: str = Header(...),
):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "DELETE FROM concept_quiz_questions WHERE id = $1::uuid AND concept_id = $2::uuid",
            question_id, concept_id,
        )
    return {"ok": True}


@router.post("/concepts/{concept_id}/quiz/approve-all")
async def approve_all_quiz(concept_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "UPDATE concept_quiz_questions SET status = 'approved' WHERE concept_id = $1::uuid AND status != 'rejected'",
            concept_id,
        )
    return {"ok": True}


class UpdateFlashcardRequest(BaseModel):
    status:   str | None = None
    position: int | None = None


@router.patch("/concepts/{concept_id}/flashcards/{card_id}")
async def update_flashcard(
    concept_id: str, card_id: str,
    req: UpdateFlashcardRequest,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    sets, vals = [], []
    if req.status   is not None: sets.append(f"status = ${len(vals)+1}");   vals.append(req.status)
    if req.position is not None: sets.append(f"position = ${len(vals)+1}"); vals.append(req.position)
    if not sets:
        return {"ok": True}
    async with get_db() as db:
        await db.execute(
            f"UPDATE concept_flashcards SET {', '.join(sets)} WHERE id = ${len(vals)+1}::uuid AND concept_id = ${len(vals)+2}::uuid",
            *vals, card_id, concept_id,
        )
    return {"ok": True}


@router.delete("/concepts/{concept_id}/flashcards/{card_id}")
async def delete_flashcard(
    concept_id: str, card_id: str, authorization: str = Header(...),
):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "DELETE FROM concept_flashcards WHERE id = $1::uuid AND concept_id = $2::uuid",
            card_id, concept_id,
        )
    return {"ok": True}


@router.post("/concepts/{concept_id}/flashcards/approve-all")
async def approve_all_flashcards(concept_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "UPDATE concept_flashcards SET status = 'approved' WHERE concept_id = $1::uuid AND status != 'rejected'",
            concept_id,
        )
    return {"ok": True}


class QuizModeRequest(BaseModel):
    quiz_mode: str  # 'ordered' | 'difficulty' | 'shuffle'


@router.patch("/concepts/{concept_id}/quiz-mode")
async def update_quiz_mode(
    concept_id: str, req: QuizModeRequest, authorization: str = Header(...),
):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "UPDATE course_concepts SET quiz_mode = $1 WHERE id = $2::uuid",
            req.quiz_mode, concept_id,
        )
    return {"ok": True}


async def _generate_quiz_bg(concept_id: str, course_id: str):
    """Background: generate quiz questions via GPT-4o, store in concept_quiz_questions."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    try:
        async with get_db() as db:
            concept = await db.fetchrow(
                "SELECT title, ai_summary, source_text FROM course_concepts WHERE id = $1::uuid",
                concept_id,
            )
            course = await db.fetchrow("SELECT subject, grade, board, teacher_id FROM courses WHERE id = $1::uuid", course_id)
            lang_val = None
            if course and course["teacher_id"]:
                lang_val = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", course["teacher_id"])

        source   = (concept["source_text"] or concept["ai_summary"] or concept["title"])
        subject  = (course["subject"] if course else None) or "General"
        language = lang_val or 'en'
        grade    = (course.get("grade") if course else None) or ""
        board    = (course.get("board") if course else None) or ""

        prompt = build_quiz_prompt(concept["title"], subject, source, language=language, grade=grade, board=board)

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=3000,
            temperature=0.3,
        )
        result = json.loads(response.choices[0].message.content)
        questions = _shuffle_quiz_options(result.get("questions", []))

        async with get_db() as db:
            await db.execute(
                "DELETE FROM concept_quiz_questions WHERE concept_id = $1::uuid", concept_id
            )
            for pos, q in enumerate(questions):
                await db.execute("""
                    INSERT INTO concept_quiz_questions
                      (concept_id, question, options, correct_idx, explanation, position, status, difficulty)
                    VALUES ($1::uuid, $2, $3::jsonb, $4, $5, $6, 'draft', $7)
                """, concept_id, q["question"], json.dumps(q["options"]),
                    q["correct_idx"], q.get("explanation", ""), pos,
                    q.get("difficulty", "medium"))
            await db.execute(
                "UPDATE course_concepts SET quiz_status = 'ready' WHERE id = $1::uuid", concept_id
            )
    except Exception as exc:
        logger.error("[quiz] concept %s failed: %s", concept_id, exc)
        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET quiz_status = 'failed' WHERE id = $1::uuid", concept_id
            )


async def _generate_flashcards_bg(concept_id: str, course_id: str):
    """Background: generate flashcard pairs via GPT-4o."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    try:
        async with get_db() as db:
            concept = await db.fetchrow(
                "SELECT title, ai_summary, source_text FROM course_concepts WHERE id = $1::uuid",
                concept_id,
            )
            lang_val = await db.fetchval("""
                SELECT u.language FROM courses c
                JOIN users u ON u.id = c.teacher_id
                WHERE c.id = $1::uuid
            """, course_id)

        source   = (concept["source_text"] or concept["ai_summary"] or concept["title"])
        language = lang_val or 'en'

        prompt = build_flashcard_prompt(concept["title"], source, language=language)

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2500,
            temperature=0.3,
        )
        result = json.loads(response.choices[0].message.content)
        cards = result.get("flashcards", [])

        async with get_db() as db:
            await db.execute(
                "DELETE FROM concept_flashcards WHERE concept_id = $1::uuid", concept_id
            )
            for pos, card in enumerate(cards):
                await db.execute("""
                    INSERT INTO concept_flashcards (concept_id, front, back, position, status)
                    VALUES ($1::uuid, $2, $3, $4, 'draft')
                """, concept_id, card["front"], card["back"], pos)
            await db.execute(
                "UPDATE course_concepts SET flashcard_status = 'ready' WHERE id = $1::uuid", concept_id
            )
    except Exception as exc:
        logger.error("[flashcards] concept %s failed: %s", concept_id, exc)
        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET flashcard_status = 'failed' WHERE id = $1::uuid", concept_id
            )


_MANIM_SUBJECTS = {
    "physics": "physics", "chemistry": "chemistry",
    "mathematics": "mathematics", "math": "mathematics", "maths": "mathematics",
    "economics": "economics", "biology": "biology",
    "science": "science",
}


def _map_manim_subject(course_subject: str | None) -> str:
    """Map a course's free-text subject to one of the Manim pipeline's known subjects."""
    s = (course_subject or "").strip().lower()
    for key, mapped in _MANIM_SUBJECTS.items():
        if key in s:
            return mapped
    return "general"


def _build_concept_video_prompt(title: str, source_text: str | None, summary: str | None, extra: str = "") -> str:
    """
    Ground Stage 1 (GPT-4o) in the concept's actual source material — same idea as
    build_studyset_prompt's "answer ONLY from the material" grounding — instead of
    handing it a bare title. Falls back to the approved summary if no source text
    was captured for this concept. `extra` lets callers (e.g. per-student remedial
    assignments) add framing without duplicating this prompt.
    """
    material = (source_text or summary or title)[:8000]
    return f"""Teach the concept "{title}" to students.
{extra}
Base your explanation strictly on the material below — do not invent facts,
numbers, or examples that aren't supported by it. If the material describes a
worked example or process, use that as the CALCULATION/worked section.

SOURCE MATERIAL:
---
{material}
---"""


async def _generate_concept_video_bg(concept_id: str, course_id: str, teacher_id: str | None = None):
    """
    Background: generate a real Manim-animated video for a concept by reusing the
    AnimLearn pipeline (services/manim.py) — the exact two-phase flow used for
    student-triggered study-set videos (routers/videos.py::_generate_video_bg),
    just sourced from the concept's approved material instead of a chat prompt.
      Phase 1 (GPT-4o)  — structured solution + cinematic [BEAT]-marked script
      Phase 2 (Claude)  — Manim scene code + SVG assets + critic pass
    """
    from services.manim import (
        generate_solution_only, generate_manim_from_solution,
        fix_manim_colors, fix_unicode_in_mathtex, ensure_numpy_import, strip_invalid_tex_weight, _trigger_video_generation,
    )

    video_id = None
    try:
        async with get_db() as db:
            concept = await db.fetchrow(
                "SELECT title, ai_summary, ai_transcript, source_text FROM course_concepts WHERE id = $1::uuid",
                concept_id,
            )
            course = await db.fetchrow("SELECT subject, grade FROM courses WHERE id = $1::uuid", course_id)

        if not concept or not (concept["ai_transcript"] or concept["ai_summary"]):
            raise ValueError("No transcript or summary — generate and approve a summary first")

        subject  = _map_manim_subject(course["subject"] if course else None)
        script   = concept["ai_transcript"] or concept["ai_summary"]
        duration = max(45, min(180, len(script) // 12))
        prompt   = _build_concept_video_prompt(concept["title"], concept["source_text"], script)

        async with get_db() as db:
            video = await db.fetchrow("""
                INSERT INTO videos (prompt, subject, language, aspect_ratio, max_duration, status)
                VALUES ($1, $2, 'en', '16:9', $3, 'pending')
                RETURNING id
            """, prompt, subject, duration)
            video_id = video["id"]
            await db.execute(
                "UPDATE course_concepts SET video_job_id = $1, video_status = 'generating', video_error = NULL WHERE id = $2::uuid",
                video_id, concept_id,
            )

        # ── Phase 1: GPT-4o structured solution + cinematic script ───────────
        logger.info("[video] concept %s: Phase 1 (GPT-4o solution) starting (video %s)", concept_id, video_id)
        solution_data = await generate_solution_only(prompt, "en", duration)

        # For science courses, force subject = "science" so Phase 2 uses the
        # science_prompt.txt (particle animations, no equations) instead of
        # whatever GPT-4o auto-detected (usually "physics" for thermal energy).
        if subject == "science":
            solution_data = {**solution_data, "subject": "science"}

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET transcript_markdown = $1, verified_solution = $2, status = 'transcript_ready', updated_at = NOW()
                WHERE id = $3
            """, solution_data["transcript_markdown"], solution_data["verified_solution"], video_id)

        # ── Phase 2: Claude Manim code + SVG assets + critic pass ────────────
        logger.info("[video] concept %s: Phase 2 (Manim code) starting (video %s)", concept_id, video_id)
        code_data = await asyncio.wait_for(
            generate_manim_from_solution(solution_data, "en", duration, "16:9"),
            timeout=900,
        )
        code     = fix_manim_colors(code_data["code"])
        code     = fix_unicode_in_mathtex(code)
        code     = ensure_numpy_import(code)
        code     = strip_invalid_tex_weight(code)
        svg_urls = code_data.get("svg_urls") or {}

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET generated_code = $1, scene_name = $2, svg_urls = $3::jsonb, status = 'queued', updated_at = NOW()
                WHERE id = $4
            """, code, code_data.get("scene_name", "MainScene"), json.dumps(svg_urls), video_id)

        logger.info("[video] concept %s: Manim code ready, triggering Cloud Run render (video %s)", concept_id, video_id)
        _trigger_video_generation(video_id, svg_urls)

        # Create a content block and inject a video card into the studio chat
        # so the teacher can see and track the video without navigating away.
        if teacher_id:
            try:
                async with get_db() as db:
                    max_pos = await db.fetchval(
                        "SELECT COALESCE(MAX(position), -1) FROM concept_content_blocks WHERE concept_id = $1::uuid",
                        concept_id,
                    )
                    block = await db.fetchrow("""
                        INSERT INTO concept_content_blocks
                          (concept_id, type, position, title, body, created_by, in_textbook, video_id)
                        VALUES ($1::uuid, 'video', $2, $3, $4, $5::uuid, false, $6)
                        RETURNING id
                    """, concept_id, int(max_pos) + 1, concept["title"], script, teacher_id, video_id)
                    block_id = str(block["id"])

                    conv = await db.fetchrow(
                        "SELECT id FROM conversations WHERE concept_id = $1::uuid", concept_id
                    )
                    if not conv:
                        course_info = await db.fetchrow("""
                            SELECT c.subject FROM course_concepts cc
                            JOIN course_units cu ON cu.id = cc.unit_id
                            JOIN courses c ON c.id = cu.course_id
                            WHERE cc.id = $1::uuid
                        """, concept_id)
                        conv = await db.fetchrow("""
                            INSERT INTO conversations
                              (user_id, title, subject, concept_id, conversation_type)
                            VALUES ($1::uuid, $2, $3, $4::uuid, 'studio') RETURNING id
                        """, teacher_id,
                            f"{concept['title']} — Authoring chat",
                            (course_info["subject"] if course_info else None), concept_id)

                    await db.execute("""
                        INSERT INTO messages (conversation_id, role, content, metadata)
                        VALUES ($1::uuid, 'assistant', '', $2::jsonb)
                    """, conv["id"], json.dumps({"content_type": "video", "block_id": block_id}))
            except Exception as exc:
                logger.error("[video] concept %s: chat card inject failed: %s", concept_id, exc)

    except asyncio.TimeoutError:
        logger.error("[video] concept %s: Phase 2 timed out after 15 min (video %s)", concept_id, video_id)
        async with get_db() as db:
            if video_id:
                await db.execute(
                    "UPDATE videos SET status = 'failed', error_message = 'Manim generation timed out — please retry', updated_at = NOW() WHERE id = $1",
                    video_id,
                )
            await db.execute(
                "UPDATE course_concepts SET video_status = 'failed', video_error = 'Manim generation timed out — please retry' WHERE id = $1::uuid",
                concept_id,
            )
    except Exception as exc:
        logger.error("[video] concept %s failed: %s", concept_id, exc, exc_info=True)
        async with get_db() as db:
            if video_id:
                await db.execute(
                    "UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW() WHERE id = $2",
                    str(exc)[:2000], video_id,
                )
            await db.execute(
                "UPDATE course_concepts SET video_status = 'failed', video_error = $1 WHERE id = $2::uuid",
                str(exc)[:2000], concept_id,
            )


# ── Asset endpoints ───────────────────────────────────────────────────────────

@router.get("/concepts/{concept_id}/assets")
async def get_concept_assets(concept_id: str, authorization: str = Header(...)):
    """Return asset statuses + content (quiz questions, flashcards)."""
    viewer_id  = decode_jwt(authorization.removeprefix("Bearer ").strip())

    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT quiz_status, flashcard_status, audio_status, video_status, video_error, video_job_id,
                   audio_duration_sec,
                   (audio_data IS NOT NULL) AS has_audio
            FROM course_concepts WHERE id = $1::uuid
        """, concept_id)
        if not concept:
            raise HTTPException(404, "Concept not found")

        video_status = concept["video_status"]
        video_error  = concept["video_error"]
        video_stage  = None

        # Video rendering happens out-of-band on Cloud Run, which writes directly
        # to the `videos` table — sync that result onto the concept on read.
        if video_status == "generating" and concept["video_job_id"]:
            video_job = await db.fetchrow(
                "SELECT status, video_url, error_message FROM videos WHERE id = $1",
                concept["video_job_id"],
            )
            if video_job:
                if video_job["status"] in ("complete", "completed"):
                    video_status = "ready"
                    video_error = None
                    await db.execute(
                        "UPDATE course_concepts SET video_status = 'ready', video_url = $1, video_error = NULL WHERE id = $2::uuid",
                        video_job["video_url"], concept_id,
                    )
                elif video_job["status"] == "failed":
                    video_status = "failed"
                    video_error = video_job["error_message"]
                    await db.execute(
                        "UPDATE course_concepts SET video_status = 'failed', video_error = $1 WHERE id = $2::uuid",
                        video_error, concept_id,
                    )
                else:
                    video_stage = video_job["status"]  # pending|transcript_ready|queued|rendering

        is_teacher = await db.fetchval(
            "SELECT account_type = 'teacher' FROM users WHERE id = $1::uuid", viewer_id
        ) or False

        if is_teacher:
            questions = await db.fetch("""
                SELECT id, question, options, correct_idx, explanation, position, status, difficulty
                FROM concept_quiz_questions
                WHERE concept_id = $1::uuid
                ORDER BY position
            """, concept_id)
            flashcards = await db.fetch("""
                SELECT id, front, back, position, status
                FROM concept_flashcards
                WHERE concept_id = $1::uuid
                ORDER BY position
            """, concept_id)
            quiz_mode = await db.fetchval(
                "SELECT quiz_mode FROM course_concepts WHERE id = $1::uuid", concept_id
            ) or 'ordered'
        else:
            questions = await db.fetch("""
                SELECT id, question, options, correct_idx, explanation, position, status, difficulty
                FROM concept_quiz_questions
                WHERE concept_id = $1::uuid AND status = 'approved'
                ORDER BY position
            """, concept_id)
            flashcards = await db.fetch("""
                SELECT cf.id, cf.front, cf.back, cf.position, cf.status, cfs.due_at
                FROM concept_flashcards cf
                LEFT JOIN concept_flashcard_state cfs
                       ON cfs.flashcard_id = cf.id AND cfs.student_id = $2::uuid
                WHERE cf.concept_id = $1::uuid AND cf.status = 'approved'
                ORDER BY COALESCE(cfs.due_at, TIMESTAMP '1970-01-01') ASC, cf.position
            """, concept_id, viewer_id)
            quiz_mode = await db.fetchval(
                "SELECT quiz_mode FROM course_concepts WHERE id = $1::uuid", concept_id
            ) or 'ordered'

    now = datetime.now(tz=timezone.utc)
    return {
        "quiz_status":       concept["quiz_status"],
        "flashcard_status":  concept["flashcard_status"],
        "audio_status":      concept["audio_status"],
        "has_audio":          bool(concept["has_audio"]),
        "audio_duration_sec": concept["audio_duration_sec"],
        "audio_url":          f"/api/courses/concepts/{concept_id}/audio" if concept["has_audio"] else None,
        "video_status":       video_status,
        "video_error":        video_error,
        "video_stage":        video_stage,
        "video_url":          f"/api/courses/concepts/{concept_id}/video" if video_status in ("ready", "approved") else None,
        "video_job_id":       concept["video_job_id"],
        "quiz_mode":          quiz_mode,
        "quiz": [
            {
                "id":          str(q["id"]),
                "question":    q["question"],
                "options":     q["options"] if isinstance(q["options"], list) else json.loads(q["options"]),
                "correct_idx": q["correct_idx"],
                "explanation": q["explanation"] or "",
                "position":    q["position"],
                "status":      q["status"],
                "difficulty":  q["difficulty"],
            }
            for q in questions
        ],
        "flashcards": [
            {
                "id":       str(f["id"]),
                "front":    f["front"],
                "back":     f["back"],
                "position": f["position"],
                "status":   f["status"],
                **({"is_due": f["due_at"] is None or f["due_at"] <= now} if "due_at" in f.keys() else {}),
            }
            for f in flashcards
        ],
    }


@router.post("/concepts/{concept_id}/generate/quiz")
async def generate_concept_quiz(
    concept_id: str,
    bg: BackgroundTasks,
    authorization: str = Header(...),
):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.quiz_status, cu.course_id
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cc.id = $1::uuid
        """, concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")
    if concept["quiz_status"] == "generating":
        raise HTTPException(409, "Quiz generation already in progress")

    async with get_db() as db:
        await db.execute(
            "UPDATE course_concepts SET quiz_status = 'generating' WHERE id = $1::uuid", concept_id
        )
    bg.add_task(_generate_quiz_bg, concept_id, str(concept["course_id"]))
    return {"ok": True, "quiz_status": "generating"}


@router.post("/concepts/{concept_id}/generate/flashcards")
async def generate_concept_flashcards(
    concept_id: str,
    bg: BackgroundTasks,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.flashcard_status, cu.course_id
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cc.id = $1::uuid
        """, concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")
    if concept["flashcard_status"] == "generating":
        raise HTTPException(409, "Flashcard generation already in progress")

    async with get_db() as db:
        await db.execute(
            "UPDATE course_concepts SET flashcard_status = 'generating' WHERE id = $1::uuid", concept_id
        )
    bg.add_task(_generate_flashcards_bg, concept_id, str(concept["course_id"]))
    return {"ok": True, "flashcard_status": "generating"}


class AssetApproveRequest(BaseModel):
    quiz:       bool = False
    flashcards: bool = False
    video:      bool = False


@router.post("/concepts/{concept_id}/assets/approve")
async def approve_concept_assets(
    concept_id: str,
    req: AssetApproveRequest,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    sets: list[str] = []
    if req.quiz:       sets.append("quiz_status = 'approved'")
    if req.flashcards: sets.append("flashcard_status = 'approved'")
    if req.video:      sets.append("video_status = 'approved'")
    if not sets:
        return {"ok": True}
    async with get_db() as db:
        await db.execute(
            f"UPDATE course_concepts SET {', '.join(sets)} WHERE id = $1::uuid", concept_id
        )
    return {"ok": True}


@router.delete("/concepts/{concept_id}/quiz")
async def delete_concept_quiz(concept_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "DELETE FROM concept_quiz_questions WHERE concept_id = $1::uuid", concept_id
        )
        await db.execute(
            "UPDATE course_concepts SET quiz_status = 'none' WHERE id = $1::uuid", concept_id
        )
    return {"ok": True}


@router.delete("/concepts/{concept_id}/flashcards")
async def delete_concept_flashcards(concept_id: str, authorization: str = Header(...)):
    await _require_teacher(authorization)
    async with get_db() as db:
        await db.execute(
            "DELETE FROM concept_flashcards WHERE concept_id = $1::uuid", concept_id
        )
        await db.execute(
            "UPDATE course_concepts SET flashcard_status = 'none' WHERE id = $1::uuid", concept_id
        )
    return {"ok": True}


@router.post("/concepts/{concept_id}/generate/video")
async def generate_concept_video(
    concept_id: str,
    bg: BackgroundTasks,
    authorization: str = Header(...),
):
    """Trigger a Manim-animated video for this concept via the AnimLearn Cloud Run pipeline."""
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.video_status, cc.ai_summary, cc.ai_transcript, cu.course_id
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            WHERE cc.id = $1::uuid
        """, concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")
    if concept["video_status"] == "generating":
        raise HTTPException(409, "Video generation already in progress")
    if not concept["ai_transcript"] and not concept["ai_summary"]:
        raise HTTPException(400, "Generate a summary first — the video is built from it")

    async with get_db() as db:
        await db.execute(
            "UPDATE course_concepts SET video_status = 'generating', video_error = NULL WHERE id = $1::uuid",
            concept_id,
        )
    bg.add_task(_generate_concept_video_bg, concept_id, str(concept["course_id"]), str(teacher_id))
    return {"ok": True, "video_status": "generating"}


class GenerateBlockVideoRequest(BaseModel):
    title:      str
    transcript: str


async def _generate_block_video_bg(
    block_id:   str,
    concept_id: str,
    title:      str,
    transcript: str,
    subject:    str | None,
    user_id:    str | None = None,
):
    """
    Background: generate a Manim video from a teacher-written transcript.
    Phase 1 (GPT-4o) creates the animation structure; the teacher's transcript
    replaces the auto-generated narration. Sets video_id on the content block
    and concept_id on the video row once the pipeline completes Phase 2.
    """
    from services.manim import (
        generate_solution_only, generate_manim_from_solution,
        fix_manim_colors, fix_unicode_in_mathtex, ensure_numpy_import, strip_invalid_tex_weight, _trigger_video_generation,
    )

    video_id = None
    try:
        manim_subject = _map_manim_subject(subject)
        duration   = max(45, min(180, len(transcript) // 12))
        gen_prompt = f"Concept: {title}\n\nScript:\n{transcript}"

        language = "en"
        if user_id:
            async with get_db() as db:
                lang_val = await db.fetchval("SELECT language FROM users WHERE id = $1::uuid", user_id)
            language = lang_val or "en"

        async with get_db() as db:
            video = await db.fetchrow("""
                INSERT INTO videos
                  (prompt, subject, language, aspect_ratio, max_duration, status, concept_id, user_id)
                VALUES ($1, $2, $3, '16:9', $4, 'pending', $5::uuid, $6::uuid)
                RETURNING id
            """, title, manim_subject, language, duration, concept_id, user_id)
            video_id = video["id"]
            await db.execute(
                "UPDATE concept_content_blocks SET video_id = $1 WHERE id = $2::uuid",
                video_id, block_id,
            )
            # Store video_id in the video-card message metadata so status is
            # recoverable even if the content block is later deleted
            await db.execute("""
                UPDATE messages
                SET metadata = metadata || jsonb_build_object('video_id', $1::int)
                WHERE metadata->>'content_type' = 'video'
                  AND metadata->>'block_id' = $2
            """, video_id, block_id)

        logger.info("[block-video] block %s: Phase 1 starting (video %s)", block_id, video_id)
        solution_data = await generate_solution_only(gen_prompt, language, duration)
        solution_data["transcript_markdown"] = transcript  # use teacher's exact words

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET transcript_markdown = $1, verified_solution = $2, status = 'transcript_ready', updated_at = NOW()
                WHERE id = $3
            """, transcript, solution_data["verified_solution"], video_id)

        logger.info("[block-video] block %s: Phase 2 starting (video %s)", block_id, video_id)
        code_data = await asyncio.wait_for(
            generate_manim_from_solution(solution_data, language, duration, "16:9"),
            timeout=900,
        )
        code     = fix_manim_colors(code_data["code"])
        code     = fix_unicode_in_mathtex(code)
        code     = ensure_numpy_import(code)
        code     = strip_invalid_tex_weight(code)
        svg_urls = code_data.get("svg_urls") or {}

        async with get_db() as db:
            await db.execute("""
                UPDATE videos
                SET generated_code = $1, scene_name = $2, svg_urls = $3::jsonb, status = 'queued', updated_at = NOW()
                WHERE id = $4
            """, code, code_data.get("scene_name", "MainScene"), json.dumps(svg_urls), video_id)

        _trigger_video_generation(video_id, svg_urls)
        logger.info("[block-video] block %s: queued for Cloud Run render (video %s)", block_id, video_id)

    except BaseException as exc:
        logger.error("[block-video] block %s failed: %s", block_id, exc, exc_info=True)
        try:
            async with get_db() as db:
                if video_id:
                    await db.execute(
                        "UPDATE videos SET status = 'failed', error_message = $1, updated_at = NOW() WHERE id = $2",
                        f"{type(exc).__name__}: {exc}"[:2000], video_id,
                    )
        except Exception as _db_err:
            logger.error("[block-video] DB update on failure failed: %s", _db_err)
        if isinstance(exc, asyncio.CancelledError):
            raise


@router.post("/concepts/{concept_id}/content-blocks/generate-video")
async def generate_block_video(
    concept_id:    str,
    req:           GenerateBlockVideoRequest,
    bg:            BackgroundTasks,
    authorization: str = Header(...),
):
    """
    Generate a Manim video from a teacher-written transcript and link it as a
    new content block on this concept. The block is created immediately (so the
    frontend can show a 'generating' state); the video pipeline runs in the background.
    """
    teacher_id = await _require_teacher(authorization)
    if not req.transcript.strip():
        raise HTTPException(400, "Transcript cannot be empty")

    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cu.course_id, c.subject FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id  = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)
    if not concept:
        raise HTTPException(404, "Concept not found")

    async with get_db() as db:
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM concept_content_blocks WHERE concept_id = $1::uuid",
            concept_id,
        )
        block = await db.fetchrow("""
            INSERT INTO concept_content_blocks
              (concept_id, type, position, title, body, created_by)
            VALUES ($1::uuid, 'video', $2, $3, $4, $5::uuid)
            RETURNING id, position, title, created_at
        """, concept_id, int(max_pos) + 1, req.title, req.transcript, teacher_id)

    bg.add_task(
        _generate_block_video_bg,
        str(block["id"]), concept_id, req.title, req.transcript, concept["subject"], teacher_id,
    )
    return {
        "id":           str(block["id"]),
        "type":         "video",
        "position":     block["position"],
        "title":        block["title"],
        "video_id":     None,
        "video_status": "pending",
        "created_at":   block["created_at"].isoformat(),
    }


@router.get("/concepts/{concept_id}/audio")
async def serve_concept_audio(concept_id: str):
    """Serve concept audio MP3 — no auth (UUID is unguessable, audio tag can't send headers)."""
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT audio_data FROM course_concepts WHERE id = $1::uuid AND audio_status IN ('ready','approved')",
            concept_id,
        )
    if not row or not row["audio_data"]:
        raise HTTPException(404, "Audio not available")
    return Response(
        content=bytes(row["audio_data"]),
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _fmt_course(r):
    return {
        "id":          str(r["id"]),
        "name":        r["name"],
        "description": r["description"],
        "subject":     r["subject"],
        "grade":       r["grade"],
        "board":       r.get("board"),
        "status":      r["status"],
        "created_at":  r["created_at"].isoformat() if r.get("created_at") else None,
    }
