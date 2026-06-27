"""
Direct messaging between a teacher and a student, scoped to a shared classroom.
One thread per (teacher, student) pair — a student in classrooms taught by two
different teachers gets two separate threads.

  GET  /api/messages/threads                — list this user's threads (other party + last message + unread)
  GET  /api/messages/thread/{other_user_id}  — full message list for one thread (marks it read)
  POST /api/messages/thread/{other_user_id}  — send a message
  GET  /api/messages/unread-count            — total unread across all threads (for a sidebar badge)
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from database import get_db
from routers.classrooms import _get_user

router = APIRouter(prefix="/api/messages", tags=["messages"])

_TEACHER_TYPES = ("teacher", "institution_admin", "super_admin")


async def _resolve_thread(authorization: str, other_user_id: str) -> tuple[str, str, str]:
    """Returns (teacher_id, student_id, caller_id) after verifying a shared classroom connects them."""
    caller_id, account_type = await _get_user(authorization)
    is_teacher = account_type in _TEACHER_TYPES
    teacher_id, student_id = (caller_id, other_user_id) if is_teacher else (other_user_id, caller_id)

    async with get_db() as db:
        enrolled = await db.fetchval("""
            SELECT 1 FROM classroom_students cs
            JOIN classrooms cl ON cl.id = cs.classroom_id
            WHERE cl.teacher_id = $1::uuid AND cs.student_id = $2::uuid
            LIMIT 1
        """, teacher_id, student_id)
    if not enrolled:
        raise HTTPException(403, "Not connected via a shared classroom")
    return teacher_id, student_id, caller_id


@router.get("/threads")
async def list_threads(authorization: str = Header(...)):
    caller_id, account_type = await _get_user(authorization)
    is_teacher = account_type in _TEACHER_TYPES

    async with get_db() as db:
        if is_teacher:
            partners = await db.fetch("""
                SELECT DISTINCT cs.student_id AS other_id, u.name, u.email
                FROM classroom_students cs
                JOIN classrooms cl ON cl.id = cs.classroom_id AND cl.teacher_id = $1::uuid
                JOIN users u       ON u.id = cs.student_id
            """, caller_id)
            msgs = await db.fetch(
                "SELECT teacher_id, student_id, sender_id, body, created_at, read_at "
                "FROM teacher_student_messages WHERE teacher_id = $1::uuid ORDER BY created_at DESC",
                caller_id,
            )
        else:
            partners = await db.fetch("""
                SELECT DISTINCT cl.teacher_id AS other_id, u.name, u.email
                FROM classroom_students cs
                JOIN classrooms cl ON cl.id = cs.classroom_id
                JOIN users u       ON u.id = cl.teacher_id
                WHERE cs.student_id = $1::uuid
            """, caller_id)
            msgs = await db.fetch(
                "SELECT teacher_id, student_id, sender_id, body, created_at, read_at "
                "FROM teacher_student_messages WHERE student_id = $1::uuid ORDER BY created_at DESC",
                caller_id,
            )

    last_by_other: dict[str, dict] = {}
    unread_by_other: dict[str, int] = {}
    for m in msgs:
        other_id = str(m["student_id"]) if is_teacher else str(m["teacher_id"])
        if other_id not in last_by_other:
            last_by_other[other_id] = m
        if str(m["sender_id"]) != caller_id and m["read_at"] is None:
            unread_by_other[other_id] = unread_by_other.get(other_id, 0) + 1

    result = []
    for p in partners:
        oid  = str(p["other_id"])
        last = last_by_other.get(oid)
        result.append({
            "id":              oid,
            "name":            p["name"],
            "email":           p["email"],
            "last_message":    last["body"] if last else None,
            "last_message_at": last["created_at"].isoformat() if last else None,
            "unread_count":    unread_by_other.get(oid, 0),
        })
    result.sort(key=lambda r: r["last_message_at"] or "", reverse=True)
    return result


@router.get("/thread/{other_user_id}")
async def get_thread(other_user_id: str, authorization: str = Header(...)):
    teacher_id, student_id, caller_id = await _resolve_thread(authorization, other_user_id)

    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, sender_id, body, created_at
            FROM teacher_student_messages
            WHERE teacher_id = $1::uuid AND student_id = $2::uuid
            ORDER BY created_at ASC
        """, teacher_id, student_id)

        await db.execute("""
            UPDATE teacher_student_messages
            SET read_at = NOW()
            WHERE teacher_id = $1::uuid AND student_id = $2::uuid
              AND sender_id != $3::uuid AND read_at IS NULL
        """, teacher_id, student_id, caller_id)

    return [
        {
            "id":         str(r["id"]),
            "sender_id":  str(r["sender_id"]),
            "body":       r["body"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "is_mine":    str(r["sender_id"]) == caller_id,
        }
        for r in rows
    ]


class SendMessageRequest(BaseModel):
    text: str


@router.post("/thread/{other_user_id}")
async def send_message(other_user_id: str, req: SendMessageRequest, authorization: str = Header(...)):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Message cannot be empty")

    teacher_id, student_id, caller_id = await _resolve_thread(authorization, other_user_id)
    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO teacher_student_messages (teacher_id, student_id, sender_id, body)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4)
            RETURNING id, created_at
        """, teacher_id, student_id, caller_id, text[:4000])

    return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}


@router.get("/unread-count")
async def get_unread_count(authorization: str = Header(...)):
    caller_id, account_type = await _get_user(authorization)
    is_teacher = account_type in _TEACHER_TYPES
    col = "teacher_id" if is_teacher else "student_id"

    async with get_db() as db:
        count = await db.fetchval(f"""
            SELECT COUNT(*) FROM teacher_student_messages
            WHERE {col} = $1::uuid AND sender_id != $1::uuid AND read_at IS NULL
        """, caller_id)
    return {"unread_count": int(count or 0)}
