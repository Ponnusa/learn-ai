"""
Classrooms router.
Teachers create and manage classrooms; students join via a 6-char code.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from database import get_db
from routers.auth import decode_jwt

router = APIRouter(prefix="/api/classrooms", tags=["classrooms"])


async def _get_user(authorization: str):
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT id, account_type, is_active FROM users WHERE id = $1::uuid", user_id
        )
    if not row or not row["is_active"]:
        raise HTTPException(403, "Account inactive or not found")
    return str(row["id"]), row["account_type"]


async def _require_teacher(authorization: str):
    user_id, account_type = await _get_user(authorization)
    if account_type not in ("teacher", "institution_admin", "super_admin"):
        raise HTTPException(403, "Teacher access required")
    return user_id


# ── Teacher: create classroom ─────────────────────────────────────────────────

class CreateClassroomRequest(BaseModel):
    name:    str
    subject: str | None = None
    grade:   str | None = None


@router.post("")
async def create_classroom(req: CreateClassroomRequest, authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO classrooms (teacher_id, name, subject, grade)
            VALUES ($1::uuid, $2, $3, $4)
            RETURNING id, name, subject, grade, join_code, is_active, created_at
        """, teacher_id, req.name, req.subject, req.grade)
    return _fmt_classroom(row, student_count=0)


# ── Teacher: list my classrooms ───────────────────────────────────────────────

@router.get("/teaching")
async def list_my_classrooms(authorization: str = Header(...)):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT c.id, c.name, c.subject, c.grade, c.join_code, c.is_active, c.created_at,
                   COUNT(cs.student_id) AS student_count
            FROM classrooms c
            LEFT JOIN classroom_students cs ON cs.classroom_id = c.id
            WHERE c.teacher_id = $1::uuid
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """, teacher_id)
    return [_fmt_classroom(r, int(r["student_count"] or 0)) for r in rows]


# ── Teacher: classroom detail + roster ────────────────────────────────────────

@router.get("/{classroom_id}")
async def get_classroom(classroom_id: str, authorization: str = Header(...)):
    user_id, account_type = await _get_user(authorization)

    async with get_db() as db:
        cls = await db.fetchrow(
            "SELECT * FROM classrooms WHERE id = $1::uuid", classroom_id
        )
        if not cls:
            raise HTTPException(404, "Classroom not found")

        # Teachers can see their own; students can see ones they joined
        is_teacher = account_type in ("teacher", "institution_admin", "super_admin")
        if is_teacher and str(cls["teacher_id"]) != user_id:
            raise HTTPException(403, "Not your classroom")
        if not is_teacher:
            enrolled = await db.fetchval("""
                SELECT 1 FROM classroom_students
                WHERE classroom_id = $1::uuid AND student_id = $2::uuid
            """, classroom_id, user_id)
            if not enrolled:
                raise HTTPException(403, "Not enrolled in this classroom")

        students = await db.fetch("""
            SELECT u.id, u.email, u.name, u.last_seen_at, cs.joined_at
            FROM classroom_students cs
            JOIN users u ON u.id = cs.student_id
            WHERE cs.classroom_id = $1::uuid
            ORDER BY cs.joined_at DESC
        """, classroom_id)

    return {
        **_fmt_classroom(cls, len(students)),
        "students": [
            {
                "id":           str(s["id"]),
                "email":        s["email"],
                "name":         s["name"],
                "joined_at":    s["joined_at"].isoformat(),
                "last_seen_at": s["last_seen_at"].isoformat() if s["last_seen_at"] else None,
            }
            for s in students
        ],
    }


# ── Teacher: archive / reopen classroom ──────────────────────────────────────

@router.patch("/{classroom_id}")
async def update_classroom(
    classroom_id: str,
    req: dict,
    authorization: str = Header(...),
):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        cls = await db.fetchrow(
            "SELECT teacher_id FROM classrooms WHERE id = $1::uuid", classroom_id
        )
        if not cls or str(cls["teacher_id"]) != teacher_id:
            raise HTTPException(403, "Not your classroom")

        sets, params = [], [classroom_id]
        if "is_active" in req:
            params.append(req["is_active"])
            sets.append(f"is_active = ${len(params)}")
        if "name" in req:
            params.append(req["name"])
            sets.append(f"name = ${len(params)}")
        if "subject" in req:
            params.append(req["subject"])
            sets.append(f"subject = ${len(params)}")
        if "grade" in req:
            params.append(req["grade"])
            sets.append(f"grade = ${len(params)}")

        if sets:
            await db.execute(
                f"UPDATE classrooms SET {', '.join(sets)} WHERE id = $1::uuid", *params
            )
    return {"ok": True}


# ── Teacher: remove a student ─────────────────────────────────────────────────

@router.delete("/{classroom_id}/students/{student_id}")
async def remove_student(
    classroom_id: str,
    student_id:   str,
    authorization: str = Header(...),
):
    teacher_id = await _require_teacher(authorization)
    async with get_db() as db:
        cls = await db.fetchrow(
            "SELECT teacher_id FROM classrooms WHERE id = $1::uuid", classroom_id
        )
        if not cls or str(cls["teacher_id"]) != teacher_id:
            raise HTTPException(403, "Not your classroom")
        await db.execute("""
            DELETE FROM classroom_students
            WHERE classroom_id = $1::uuid AND student_id = $2::uuid
        """, classroom_id, student_id)
    return {"ok": True}


# ── Student: join classroom by code ──────────────────────────────────────────

class JoinClassroomRequest(BaseModel):
    code: str


@router.post("/join")
async def join_classroom(req: JoinClassroomRequest, authorization: str = Header(...)):
    user_id, _ = await _get_user(authorization)
    async with get_db() as db:
        cls = await db.fetchrow("""
            SELECT id, name, subject, grade, is_active
            FROM classrooms WHERE join_code = $1
        """, req.code.upper().strip())

        if not cls:
            raise HTTPException(404, "Invalid join code — check with your teacher")
        if not cls["is_active"]:
            raise HTTPException(400, "This classroom is no longer active")

        already = await db.fetchval("""
            SELECT 1 FROM classroom_students
            WHERE classroom_id = $1 AND student_id = $2::uuid
        """, cls["id"], user_id)
        if already:
            return {"message": "Already enrolled", "classroom": _fmt_classroom(cls, 0)}

        await db.execute("""
            INSERT INTO classroom_students (classroom_id, student_id)
            VALUES ($1, $2::uuid)
        """, cls["id"], user_id)

    return {"message": f"Joined {cls['name']}", "classroom": _fmt_classroom(cls, 0)}


# ── Student: list joined classrooms ──────────────────────────────────────────

@router.get("/enrolled")
async def my_classrooms(authorization: str = Header(...)):
    user_id, _ = await _get_user(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT c.id, c.name, c.subject, c.grade, c.join_code, c.is_active, c.created_at,
                   u.name AS teacher_name, u.email AS teacher_email,
                   COUNT(cs2.student_id) AS student_count
            FROM classroom_students cs
            JOIN classrooms c       ON c.id  = cs.classroom_id
            JOIN users u            ON u.id  = c.teacher_id
            LEFT JOIN classroom_students cs2 ON cs2.classroom_id = c.id
            WHERE cs.student_id = $1::uuid
            GROUP BY c.id, u.name, u.email
            ORDER BY cs.joined_at DESC
        """, user_id)
    return [
        {
            **_fmt_classroom(r, int(r["student_count"] or 0)),
            "teacher_name":  r["teacher_name"],
            "teacher_email": r["teacher_email"],
        }
        for r in rows
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_classroom(r, student_count: int = 0):
    return {
        "id":            str(r["id"]),
        "name":          r["name"],
        "subject":       r["subject"],
        "grade":         r["grade"],
        "join_code":     r["join_code"],
        "is_active":     r["is_active"],
        "student_count": student_count,
        "created_at":    r["created_at"].isoformat() if r.get("created_at") else None,
    }
