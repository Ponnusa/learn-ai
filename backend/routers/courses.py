"""
Course builder router — teachers create courses (units + concepts),
optionally imported from a syllabus PDF, then assign to classrooms.
"""
import asyncio
import json
import logging
import re
import tempfile
import os
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header, Request, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel

from database import get_db
from routers.auth import decode_jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/courses", tags=["courses"])


async def _summarize_concepts_bg(concept_ids: list[str], course_id: str):
    """Background: generate AI summary + transcript per concept, one at a time."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT name, subject FROM courses WHERE id = $1::uuid", course_id
        )

    for concept_id in concept_ids:
        try:
            async with get_db() as db:
                concept = await db.fetchrow(
                    "SELECT title, description, source_text FROM course_concepts WHERE id = $1::uuid",
                    concept_id,
                )
            if not concept:
                continue

            source = concept["source_text"] or concept["description"] or concept["title"]
            subject = (course["subject"] if course else None) or "General"

            prompt = f"""You are an expert educator creating study material for students.

Concept: {concept['title']}
Subject: {subject}

Source material (from the chapter):
---
{source}
---

Create two things grounded strictly in the source above:

1. SUMMARY — 3-4 clear paragraphs for a student:
   • Start with a plain-language definition
   • Explain the key ideas with a concrete example
   • Keep it engaging and jargon-free

2. TRANSCRIPT — a 2-minute video narration script:
   • Conversational spoken-word style
   • Open with "In this lesson, we'll explore [concept]..."
   • Mirror the summary content but as natural speech
   • End with a brief recap sentence

Return ONLY valid JSON:
{{"summary": "...", "transcript": "..."}}"""

            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.4,
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


@router.post("")
async def create_course(req: CreateCourseRequest, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO courses (teacher_id, name, description, subject, grade)
            VALUES ($1::uuid, $2, $3, $4, $5)
            RETURNING id, name, description, subject, grade, status, created_at
        """, teacher_id, req.name, req.description, req.subject, req.grade)
    return _fmt_course(row)


@router.get("/mine")
async def list_my_courses(authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT c.id, c.name, c.description, c.subject, c.grade, c.status, c.created_at,
                   COUNT(DISTINCT cu.id) AS unit_count,
                   COUNT(DISTINCT cc.id) AS concept_count
            FROM courses c
            LEFT JOIN course_units    cu ON cu.course_id = c.id
            LEFT JOIN course_concepts cc ON cc.unit_id   = cu.id
            WHERE c.teacher_id = $1::uuid
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """, teacher_id)
    return [
        {**_fmt_course(r), "unit_count": int(r["unit_count"] or 0), "concept_count": int(r["concept_count"] or 0)}
        for r in rows
    ]


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
            SELECT id, title, description, position FROM course_units
            WHERE course_id = $1::uuid ORDER BY position, created_at
        """, course_id)

        unit_ids = [str(u["id"]) for u in units]
        concepts = []
        if unit_ids:
            concepts = await db.fetch("""
                SELECT cc.id, cc.unit_id, cc.title, cc.description,
                       cc.study_set_id, cc.position,
                       ss.status AS ss_status
                FROM course_concepts cc
                LEFT JOIN study_sets ss ON ss.id = cc.study_set_id
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
                "id":           str(c["id"]),
                "title":        c["title"],
                "description":  c["description"],
                "study_set_id": str(c["study_set_id"]) if c["study_set_id"] else None,
                "ss_status":    c["ss_status"],
                "position":     c["position"],
            })

    return {
        **_fmt_course(course),
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
        "classrooms": [{"id": str(cl["id"]), "name": cl["name"]} for cl in classrooms],
    }


class UpdateCourseRequest(BaseModel):
    name:        str | None = None
    description: str | None = None
    subject:     str | None = None
    grade:       str | None = None
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
            INSERT INTO course_concepts (unit_id, title, description, position)
            VALUES ($1::uuid, $2, $3, $4)
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
            "SELECT id, name, subject FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
    if not course:
        raise HTTPException(404, "Course not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(400, "File too large — max 20 MB")

    from services.studyset_processor import extract_text_from_pdf
    from openai import AsyncOpenAI

    text, page_count = extract_text_from_pdf(file_bytes)
    truncated = text[:80_000]

    client = AsyncOpenAI()
    prompt = f"""You are an expert curriculum designer. Analyze the syllabus/textbook below and extract a structured course outline.

Course name: {course["name"]}
Subject: {course["subject"] or "General"}

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
- Follow the order as it appears in the syllabus

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
    Student taps a concept:
    1. Auto-create a study_set if none exists yet (links it to the concept)
    2. Record progress (mark visited)
    Returns study_set_id so frontend can navigate to /study/[id]
    """
    student_id = await _get_student(authorization)

    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT cc.id, cc.title, cc.description, cc.study_set_id, cc.unit_id,
                   cu.course_id, c.subject
            FROM course_concepts cc
            JOIN course_units cu ON cu.id = cc.unit_id
            JOIN courses c       ON c.id  = cu.course_id
            WHERE cc.id = $1::uuid
        """, concept_id)

        if not concept:
            raise HTTPException(404, "Concept not found")

        study_set_id = concept["study_set_id"]

        # Upsert progress (do NOT auto-create study set — teacher creates it)
        await db.execute("""
            INSERT INTO student_concept_progress
              (student_id, concept_id, course_id, visited, visited_at, last_seen_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, true, NOW(), NOW())
            ON CONFLICT (student_id, concept_id)
            DO UPDATE SET visited = true, visited_at = COALESCE(student_concept_progress.visited_at, NOW()),
                          last_seen_at = NOW()
        """, student_id, concept_id, str(concept["course_id"]))

    return {"study_set_id": str(study_set_id)}


# ── Chapter upload → AI pipeline ─────────────────────────────────────────────

@router.post("/{course_id}/chapters")
async def upload_chapter(
    course_id:     str,
    bg:            BackgroundTasks,
    authorization: str        = Header(...),
    file:          UploadFile = File(...),
):
    """
    Upload a chapter PDF:
    1. AI extracts concepts with verbatim source chunks (sync, fast)
    2. Creates a unit + concepts in DB with pipeline_status='summarizing'
    3. Background job generates ai_summary + ai_transcript per concept
    """
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id, name, subject FROM courses WHERE id = $1::uuid AND teacher_id = $2::uuid",
            course_id, teacher_id,
        )
    if not course:
        raise HTTPException(404, "Course not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    file_bytes = await file.read()
    if len(file_bytes) > 30 * 1024 * 1024:
        raise HTTPException(400, "File too large — max 30 MB")

    from services.studyset_processor import extract_text_from_pdf
    from openai import AsyncOpenAI

    text, page_count = extract_text_from_pdf(file_bytes)
    truncated = text[:80_000]

    client = AsyncOpenAI()
    extract_prompt = f"""You are an expert educator. Analyze this chapter and extract the key concepts students must learn.

Course: {course['name']}
Subject: {course['subject'] or 'General'}

For EACH concept, include the EXACT verbatim paragraph(s) from the text it is based on.

Return ONLY valid JSON:
{{
  "chapter_title": "...",
  "concepts": [
    {{
      "title": "Concise concept name",
      "description": "One sentence: what the student will understand",
      "source_text": "The exact verbatim sentences/paragraphs from the text that cover this concept"
    }}
  ]
}}

Rules:
- 4–12 concepts, in the order they appear in the text
- source_text must be a direct quote from the document
- Each concept = one distinct learnable idea

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
    chapter_title = result.get("chapter_title") or file.filename.replace(".pdf", "")

    async with get_db() as db:
        chapter_row = await db.fetchrow("""
            INSERT INTO course_chapters (course_id, filename, page_count, concept_count, status, pdf_data)
            VALUES ($1::uuid, $2, $3, $4, 'ready', $5) RETURNING id
        """, course_id, file.filename, page_count, len(concepts_raw), file_bytes)

        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM course_units WHERE course_id = $1::uuid",
            course_id,
        )
        unit_row = await db.fetchrow("""
            INSERT INTO course_units (course_id, title, description, position)
            VALUES ($1::uuid, $2, $3, $4) RETURNING id
        """, course_id, chapter_title, f"Source: {file.filename}", int(max_pos) + 1)

        concept_ids = []
        for pos, c in enumerate(concepts_raw):
            row = await db.fetchrow("""
                INSERT INTO course_concepts
                  (unit_id, title, description, source_text, pipeline_status, position, chapter_ref)
                VALUES ($1::uuid, $2, $3, $4, 'summarizing', $5, $6)
                RETURNING id
            """, str(unit_row["id"]),
                c.get("title", ""), c.get("description", ""),
                c.get("source_text", ""), pos, str(chapter_row["id"]))
            concept_ids.append(str(row["id"]))

    bg.add_task(_summarize_concepts_bg, concept_ids, course_id)

    return {
        "chapter_id":    str(chapter_row["id"]),
        "chapter_title": chapter_title,
        "unit_id":       str(unit_row["id"]),
        "concept_count": len(concept_ids),
        "concept_ids":   concept_ids,
        "page_count":    page_count,
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

    return {
        "is_processing": counts.get("summarizing", 0) > 0,
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
                   cc.chapter_ref,
                   (cc.audio_data IS NOT NULL) AS has_audio,
                   (cc.video_data IS NOT NULL) AS has_video,
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
        "quiz_status":      concept["quiz_status"],
        "flashcard_status": concept["flashcard_status"],
        "audio_status":     concept["audio_status"],
        "video_status":     concept["video_status"],
        "has_audio":        bool(concept["has_audio"]),
        "has_video":        bool(concept["has_video"]),
        "audio_url":        f"/api/courses/concepts/{concept_id}/audio" if concept["has_audio"] else None,
        "video_url":        f"/api/courses/concepts/{concept_id}/video" if concept["has_video"] else None,
        "images": [
            {
                "id":       str(img["id"]),
                "url":      f"/api/courses/concepts/images/{img['id']}",
                "caption":  img["caption"] or "",
                "position": img["position"],
            }
            for img in images
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


@router.get("/concepts/{concept_id}/video")
async def serve_concept_video(concept_id: str, request: Request):
    """
    Serve concept MP4 — no auth (UUID is unguessable).
    Supports HTTP range requests so the browser video player can seek.
    """
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT video_data FROM course_concepts WHERE id = $1::uuid AND video_status IN ('ready','approved')",
            concept_id,
        )
    if not row or not row["video_data"]:
        raise HTTPException(404, "Video not available")

    video_bytes = bytes(row["video_data"])
    file_size   = len(video_bytes)
    range_header = request.headers.get("range")

    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if m:
            start = int(m.group(1))
            end   = int(m.group(2)) if m.group(2) else file_size - 1
            end   = min(end, file_size - 1)
            return Response(
                content=video_bytes[start:end + 1],
                status_code=206,
                media_type="video/mp4",
                headers={
                    "Content-Range":  f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges":  "bytes",
                    "Content-Length": str(end - start + 1),
                },
            )

    return Response(
        content=video_bytes,
        media_type="video/mp4",
        headers={
            "Accept-Ranges":  "bytes",
            "Content-Length": str(file_size),
            "Cache-Control":  "public, max-age=86400",
        },
    )


# ── Asset generation backgrounds ─────────────────────────────────────────────

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
            course = await db.fetchrow("SELECT subject FROM courses WHERE id = $1::uuid", course_id)

        source  = (concept["source_text"] or concept["ai_summary"] or concept["title"])
        subject = (course["subject"] if course else None) or "General"

        prompt = f"""You are an expert educator. Create 6 multiple-choice quiz questions to test student understanding.

Concept: {concept['title']}
Subject: {subject}

Source material:
---
{source[:6000]}
---

Rules:
- Each question must be answerable from the source material
- All 4 options must be plausible (avoid obviously wrong distractors)
- Include a 1-2 sentence explanation for the correct answer
- Vary difficulty: 2 recall, 2 comprehension, 2 application questions

Return ONLY valid JSON:
{{"questions": [{{"question": "...", "options": ["A", "B", "C", "D"], "correct_idx": 0, "explanation": "..."}}]}}"""

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=3000,
            temperature=0.3,
        )
        result = json.loads(response.choices[0].message.content)
        questions = result.get("questions", [])

        async with get_db() as db:
            await db.execute(
                "DELETE FROM concept_quiz_questions WHERE concept_id = $1::uuid", concept_id
            )
            for pos, q in enumerate(questions):
                await db.execute("""
                    INSERT INTO concept_quiz_questions
                      (concept_id, question, options, correct_idx, explanation, position)
                    VALUES ($1::uuid, $2, $3::jsonb, $4, $5, $6)
                """, concept_id, q["question"], json.dumps(q["options"]),
                    q["correct_idx"], q.get("explanation", ""), pos)
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

        source = (concept["source_text"] or concept["ai_summary"] or concept["title"])

        prompt = f"""You are an expert educator. Create 10 flashcards to help students memorise key terms and ideas.

Concept: {concept['title']}

Source material:
---
{source[:6000]}
---

Rules:
- Front: term, definition prompt, or short question (max 12 words)
- Back: precise answer or definition (1-2 sentences)
- Cover key vocabulary, key facts, and cause-effect relationships
- Keep language student-friendly

Return ONLY valid JSON:
{{"flashcards": [{{"front": "...", "back": "..."}}]}}"""

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
                    INSERT INTO concept_flashcards (concept_id, front, back, position)
                    VALUES ($1::uuid, $2, $3, $4)
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


def _render_title_slide(title: str, out_path: str, size=(1280, 720)):
    """Render a dark title slide with centered, word-wrapped text using Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", size, color=(26, 26, 46))
    draw = ImageDraw.Draw(img)

    font_size = 54
    font = ImageFont.load_default(size=font_size)

    max_width = size[0] - 160
    words = title.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    line_height = font_size + 16
    total_height = line_height * len(lines)
    y = (size[1] - total_height) / 2
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (size[0] - w) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_height

    img.save(out_path)


async def _generate_video_bg(concept_id: str):
    """
    Background: create MP4 from TTS audio + a rendered title slide using ffmpeg.
    Requires ffmpeg to be installed on the server (provided via imageio-ffmpeg).
    """
    try:
        async with get_db() as db:
            concept = await db.fetchrow(
                "SELECT title, audio_data FROM course_concepts WHERE id = $1::uuid", concept_id
            )
        if not concept or not concept["audio_data"]:
            raise ValueError("No audio — generate and approve audio first")

        audio_bytes = bytes(concept["audio_data"])
        raw_title = (concept["title"] or "Concept")[:80]

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            slide_path = os.path.join(tmpdir, "slide.png")
            video_path = os.path.join(tmpdir, "video.mp4")

            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            _render_title_slide(raw_title, slide_path)

            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

            cmd = [
                ffmpeg_exe, "-y",
                "-loop", "1", "-i", slide_path,
                "-i", audio_path,
                "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast", "-crf", "30",
                "-c:a", "aac", "-b:a", "64k",
                "-pix_fmt", "yuv420p",
                "-shortest", "-movflags", "+faststart",
                video_path,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {stderr.decode()[-500:]}")

            with open(video_path, "rb") as f:
                video_bytes = f.read()

        async with get_db() as db:
            await db.execute("""
                UPDATE course_concepts
                SET video_data = $1, video_status = 'ready', video_error = NULL
                WHERE id = $2::uuid
            """, video_bytes, concept_id)

    except Exception as exc:
        logger.error("[video] concept %s failed: %s", concept_id, exc, exc_info=True)
        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET video_status = 'failed', video_error = $1 WHERE id = $2::uuid",
                str(exc)[:2000], concept_id,
            )


async def _generate_audio_bg(concept_id: str):
    """Background: TTS via OpenAI — converts ai_transcript to MP3 and stores as bytea."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    try:
        async with get_db() as db:
            concept = await db.fetchrow(
                "SELECT ai_transcript, ai_summary, title FROM course_concepts WHERE id = $1::uuid",
                concept_id,
            )

        script = concept["ai_transcript"] or concept["ai_summary"] or concept["title"]
        if not script:
            raise ValueError("No transcript or summary to convert")

        response = await client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=script[:4096],
        )
        audio_bytes = response.content

        # Rough duration: TTS ~150 words/min, ~5 chars/word
        duration_sec = max(1, len(script) // 25)

        async with get_db() as db:
            await db.execute("""
                UPDATE course_concepts
                SET audio_data = $1, audio_duration_sec = $2, audio_status = 'ready'
                WHERE id = $3::uuid
            """, audio_bytes, duration_sec, concept_id)

    except Exception as exc:
        logger.error("[audio] concept %s failed: %s", concept_id, exc)
        async with get_db() as db:
            await db.execute(
                "UPDATE course_concepts SET audio_status = 'failed' WHERE id = $1::uuid", concept_id
            )


# ── Asset endpoints ───────────────────────────────────────────────────────────

@router.get("/concepts/{concept_id}/assets")
async def get_concept_assets(concept_id: str, authorization: str = Header(...)):
    """Return asset statuses + content (quiz questions, flashcards)."""
    decode_jwt(authorization.removeprefix("Bearer ").strip())

    async with get_db() as db:
        concept = await db.fetchrow("""
            SELECT quiz_status, flashcard_status, audio_status, video_status, video_error,
                   audio_duration_sec,
                   (audio_data IS NOT NULL) AS has_audio
            FROM course_concepts WHERE id = $1::uuid
        """, concept_id)
        if not concept:
            raise HTTPException(404, "Concept not found")

        questions = await db.fetch("""
            SELECT id, question, options, correct_idx, explanation, position
            FROM concept_quiz_questions
            WHERE concept_id = $1::uuid
            ORDER BY position
        """, concept_id)

        flashcards = await db.fetch("""
            SELECT id, front, back, position
            FROM concept_flashcards
            WHERE concept_id = $1::uuid
            ORDER BY position
        """, concept_id)

    return {
        "quiz_status":       concept["quiz_status"],
        "flashcard_status":  concept["flashcard_status"],
        "audio_status":      concept["audio_status"],
        "has_audio":          bool(concept["has_audio"]),
        "audio_duration_sec": concept["audio_duration_sec"],
        "audio_url":          f"/api/courses/concepts/{concept_id}/audio" if concept["has_audio"] else None,
        "video_status":       concept["video_status"],
        "video_error":        concept["video_error"],
        "video_url":          f"/api/courses/concepts/{concept_id}/video" if concept["video_status"] in ("ready", "approved") else None,
        "quiz": [
            {
                "id":          str(q["id"]),
                "question":    q["question"],
                "options":     q["options"] if isinstance(q["options"], list) else json.loads(q["options"]),
                "correct_idx": q["correct_idx"],
                "explanation": q["explanation"] or "",
                "position":    q["position"],
            }
            for q in questions
        ],
        "flashcards": [
            {
                "id":       str(f["id"]),
                "front":    f["front"],
                "back":     f["back"],
                "position": f["position"],
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


@router.post("/concepts/{concept_id}/generate/audio")
async def generate_concept_audio(
    concept_id: str,
    bg: BackgroundTasks,
    authorization: str = Header(...),
):
    await _require_teacher(authorization)
    async with get_db() as db:
        concept = await db.fetchrow(
            "SELECT id, audio_status, ai_transcript, ai_summary FROM course_concepts WHERE id = $1::uuid",
            concept_id,
        )
    if not concept:
        raise HTTPException(404, "Concept not found")
    if concept["audio_status"] == "generating":
        raise HTTPException(409, "Audio generation already in progress")
    if not concept["ai_transcript"] and not concept["ai_summary"]:
        raise HTTPException(400, "Generate a summary/transcript first")

    async with get_db() as db:
        await db.execute(
            "UPDATE course_concepts SET audio_status = 'generating' WHERE id = $1::uuid", concept_id
        )
    bg.add_task(_generate_audio_bg, concept_id)
    return {"ok": True, "audio_status": "generating"}


class AssetApproveRequest(BaseModel):
    quiz:       bool = False
    flashcards: bool = False
    audio:      bool = False
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
    if req.audio:      sets.append("audio_status = 'approved'")
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
    """Trigger MP4 video generation from approved TTS audio + title slide (requires ffmpeg)."""
    await _require_teacher(authorization)
    async with get_db() as db:
        concept = await db.fetchrow(
            "SELECT id, video_status, audio_status, audio_data FROM course_concepts WHERE id = $1::uuid",
            concept_id,
        )
    if not concept:
        raise HTTPException(404, "Concept not found")
    if concept["video_status"] == "generating":
        raise HTTPException(409, "Video generation already in progress")
    if not concept["audio_data"]:
        raise HTTPException(400, "Generate and approve audio first — video uses TTS audio as narration")

    async with get_db() as db:
        await db.execute(
            "UPDATE course_concepts SET video_status = 'generating', video_error = NULL WHERE id = $1::uuid",
            concept_id,
        )
    bg.add_task(_generate_video_bg, concept_id)
    return {"ok": True, "video_status": "generating"}


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
        "status":      r["status"],
        "created_at":  r["created_at"].isoformat() if r.get("created_at") else None,
    }
