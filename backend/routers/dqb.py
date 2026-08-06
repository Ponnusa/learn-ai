"""
Driving Question Board (DQB) — per classroom+course shared question board.

Students post questions about the unit driving question and mark their own
understanding as they discover answers through the unit.

Status values:
  wondering     — ❓ I don't understand this yet
  getting_there — ✓  I'm starting to understand
  understood    — ✓✓ I understand this now

Endpoints:
  GET    /api/dqb/{classroom_id}/{course_id}          — list all questions
  POST   /api/dqb/{classroom_id}/{course_id}          — student posts a question
  PATCH  /api/dqb/questions/{question_id}             — update own question status/text
  DELETE /api/dqb/questions/{question_id}             — delete own question (teacher can delete any)
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from database import get_db
from routers.auth import decode_jwt

router = APIRouter(prefix="/api/dqb", tags=["dqb"])

_STATUSES = {"wondering", "getting_there", "understood"}
_TEACHER_TYPES = {"teacher", "institution_admin", "super_admin"}


async def _get_user(authorization: str):
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT id, account_type, name, is_active FROM users WHERE id = $1::uuid", user_id
        )
    if not row or not row["is_active"]:
        raise HTTPException(403, "Account inactive")
    return str(row["id"]), row["account_type"], row["name"]


async def _assert_classroom_access(user_id: str, account_type: str, classroom_id: str, course_id: str):
    """Verify the user has access to this classroom+course pair."""
    async with get_db() as db:
        if account_type in _TEACHER_TYPES:
            # Teacher must own the course
            ok = await db.fetchval("""
                SELECT 1 FROM classroom_courses cc
                JOIN courses c ON c.id = cc.course_id
                WHERE cc.classroom_id = $1::uuid AND cc.course_id = $2::uuid
                  AND c.teacher_id = $3::uuid
            """, classroom_id, course_id, user_id)
        else:
            # Student must be enrolled in the classroom and have access to the course
            ok = await db.fetchval("""
                SELECT 1 FROM classroom_students cs
                JOIN classroom_courses cc ON cc.classroom_id = cs.classroom_id
                WHERE cs.classroom_id = $1::uuid AND cc.course_id = $2::uuid
                  AND cs.student_id = $3::uuid
            """, classroom_id, course_id, user_id)
    if not ok:
        raise HTTPException(403, "Access denied to this classroom/course")


# ── List questions ────────────────────────────────────────────────────────────

@router.get("/{classroom_id}/{course_id}")
async def list_questions(classroom_id: str, course_id: str, authorization: str = Header(...)):
    user_id, account_type, _ = await _get_user(authorization)
    await _assert_classroom_access(user_id, account_type, classroom_id, course_id)

    async with get_db() as db:
        rows = await db.fetch("""
            SELECT q.id, q.question, q.status, q.created_at, q.updated_at,
                   q.student_id,
                   u.name AS student_name
            FROM dqb_questions q
            JOIN users u ON u.id = q.student_id
            WHERE q.classroom_id = $1::uuid AND q.course_id = $2::uuid
            ORDER BY q.created_at ASC
        """, classroom_id, course_id)

    is_teacher = account_type in _TEACHER_TYPES
    return [
        {
            "id":           str(r["id"]),
            "question":     r["question"],
            "status":       r["status"],
            "created_at":   r["created_at"].isoformat(),
            "updated_at":   r["updated_at"].isoformat(),
            "student_id":   str(r["student_id"]),
            "student_name": r["student_name"] if is_teacher else (
                r["student_name"].split()[0] if r["student_name"] else "Student"
            ),
            "is_own":       str(r["student_id"]) == user_id,
        }
        for r in rows
    ]


# ── Post a question ───────────────────────────────────────────────────────────

class PostQuestionRequest(BaseModel):
    question: str


@router.post("/{classroom_id}/{course_id}")
async def post_question(
    classroom_id: str,
    course_id: str,
    req: PostQuestionRequest,
    authorization: str = Header(...),
):
    user_id, account_type, _ = await _get_user(authorization)
    await _assert_classroom_access(user_id, account_type, classroom_id, course_id)

    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Question cannot be empty")
    if len(question) > 500:
        raise HTTPException(400, "Question too long (max 500 characters)")

    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO dqb_questions (classroom_id, course_id, student_id, question, status)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'wondering')
            RETURNING id, question, status, created_at, updated_at
        """, classroom_id, course_id, user_id, question)

    return {
        "id":         str(row["id"]),
        "question":   row["question"],
        "status":     row["status"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "is_own":     True,
    }


# ── Update a question ─────────────────────────────────────────────────────────

class UpdateQuestionRequest(BaseModel):
    status:   str | None = None
    question: str | None = None


@router.patch("/questions/{question_id}")
async def update_question(
    question_id: str,
    req: UpdateQuestionRequest,
    authorization: str = Header(...),
):
    user_id, account_type, _ = await _get_user(authorization)

    async with get_db() as db:
        existing = await db.fetchrow(
            "SELECT student_id FROM dqb_questions WHERE id = $1::uuid", question_id
        )
    if not existing:
        raise HTTPException(404, "Question not found")
    if str(existing["student_id"]) != user_id and account_type not in _TEACHER_TYPES:
        raise HTTPException(403, "Can only update your own questions")

    updates, params = [], [question_id]
    if req.status is not None:
        if req.status not in _STATUSES:
            raise HTTPException(400, f"status must be one of {_STATUSES}")
        params.append(req.status)
        updates.append(f"status = ${len(params)}")
    if req.question is not None:
        q = req.question.strip()
        if not q:
            raise HTTPException(400, "Question cannot be empty")
        params.append(q)
        updates.append(f"question = ${len(params)}")
    if not updates:
        raise HTTPException(400, "Nothing to update")

    updates.append("updated_at = NOW()")
    async with get_db() as db:
        row = await db.fetchrow(
            f"UPDATE dqb_questions SET {', '.join(updates)} WHERE id = $1::uuid RETURNING id, question, status, updated_at",
            *params,
        )
    return {"id": str(row["id"]), "question": row["question"], "status": row["status"]}


# ── Delete a question ─────────────────────────────────────────────────────────

@router.delete("/questions/{question_id}")
async def delete_question(question_id: str, authorization: str = Header(...)):
    user_id, account_type, _ = await _get_user(authorization)

    async with get_db() as db:
        existing = await db.fetchrow(
            "SELECT student_id FROM dqb_questions WHERE id = $1::uuid", question_id
        )
    if not existing:
        raise HTTPException(404, "Question not found")
    if str(existing["student_id"]) != user_id and account_type not in _TEACHER_TYPES:
        raise HTTPException(403, "Can only delete your own questions")

    async with get_db() as db:
        await db.execute("DELETE FROM dqb_questions WHERE id = $1::uuid", question_id)
    return {"ok": True}
