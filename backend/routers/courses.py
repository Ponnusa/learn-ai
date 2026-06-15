"""
Course builder router — teachers create courses (units + concepts),
optionally imported from a syllabus PDF, then assign to classrooms.
"""
import json
import logging
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from pydantic import BaseModel

from database import get_db
from routers.auth import decode_jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/courses", tags=["courses"])


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

        # Create study set on first visit if not yet linked
        if not study_set_id:
            ss = await db.fetchrow("""
                INSERT INTO study_sets (user_id, title, subject, description, status)
                VALUES ($1::uuid, $2, $3, $4, 'empty')
                RETURNING id
            """, student_id, concept["title"], concept["subject"],
                concept["description"])
            study_set_id = ss["id"]

            await db.execute("""
                UPDATE course_concepts SET study_set_id = $1 WHERE id = $2::uuid
            """, study_set_id, concept_id)

        # Upsert progress
        await db.execute("""
            INSERT INTO student_concept_progress
              (student_id, concept_id, course_id, visited, visited_at, last_seen_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, true, NOW(), NOW())
            ON CONFLICT (student_id, concept_id)
            DO UPDATE SET visited = true, visited_at = COALESCE(student_concept_progress.visited_at, NOW()),
                          last_seen_at = NOW()
        """, student_id, concept_id, str(concept["course_id"]))

    return {"study_set_id": str(study_set_id)}


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
