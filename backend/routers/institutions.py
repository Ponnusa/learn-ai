"""
Institution router — institution admin manages teachers and students.
All routes require account_type = 'institution_admin'.
"""
import secrets
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional

from database import get_db
from routers.auth import decode_jwt
from config import settings

router = APIRouter(prefix="/api/institutions", tags=["institutions"])


async def _require_institution_admin(authorization: str = Header(...)):
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT id, account_type FROM users WHERE id = $1::uuid", user_id
        )
    if not row or row["account_type"] not in ("institution_admin", "super_admin"):
        raise HTTPException(403, "Institution admin access required")
    return user_id


async def _get_admin_institution(user_id: str, db):
    row = await db.fetchrow("""
        SELECT institution_id FROM institution_members
        WHERE user_id = $1::uuid AND role = 'admin' AND status = 'active'
    """, user_id)
    if not row:
        raise HTTPException(403, "No institution found for this admin")
    return str(row["institution_id"])


# ── Institution overview ──────────────────────────────────────────────────────

@router.get("/{institution_id}")
async def get_institution(institution_id: str, authorization: str = Header(...)):
    user_id = await _require_institution_admin(authorization)
    async with get_db() as db:
        inst = await db.fetchrow(
            "SELECT * FROM institutions WHERE id = $1::uuid", institution_id
        )
        if not inst:
            raise HTTPException(404, "Institution not found")

        teachers = await db.fetchval("""
            SELECT COUNT(*) FROM institution_members
            WHERE institution_id = $1::uuid AND role = 'teacher' AND status = 'active'
        """, institution_id)

        students = await db.fetchval("""
            SELECT COUNT(*) FROM institution_members
            WHERE institution_id = $1::uuid AND role = 'student' AND status = 'active'
        """, institution_id)

    return {
        "id":           str(inst["id"]),
        "name":         inst["name"],
        "type":         inst["type"],
        "plan":         inst["plan"],
        "max_teachers": inst["max_teachers"],
        "max_students": inst["max_students"],
        "teacher_count": int(teachers or 0),
        "student_count": int(students or 0),
        "email_domain": inst["email_domain"],
        "country":      inst["country"],
    }


# ── List members ──────────────────────────────────────────────────────────────

@router.get("/{institution_id}/members")
async def list_members(
    institution_id: str,
    role: str = "teacher",
    authorization: str = Header(...),
):
    await _require_institution_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT u.id, u.email, u.name, u.last_seen_at, im.status, im.joined_at
            FROM institution_members im
            JOIN users u ON u.id = im.user_id
            WHERE im.institution_id = $1::uuid AND im.role = $2
            ORDER BY im.joined_at DESC
        """, institution_id, role)
    return [
        {
            "id":          str(r["id"]),
            "email":       r["email"],
            "name":        r["name"],
            "status":      r["status"],
            "joined_at":   r["joined_at"].isoformat() if r["joined_at"] else None,
            "last_seen_at": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
        }
        for r in rows
    ]


# ── Invite a teacher ──────────────────────────────────────────────────────────

class InviteTeacherRequest(BaseModel):
    email: EmailStr
    name:  str | None = None


@router.post("/{institution_id}/teachers/invite")
async def invite_teacher(
    institution_id: str,
    req: InviteTeacherRequest,
    authorization: str = Header(...),
):
    user_id = await _require_institution_admin(authorization)
    async with get_db() as db:
        inst = await db.fetchrow(
            "SELECT max_teachers FROM institutions WHERE id = $1::uuid", institution_id
        )
        if not inst:
            raise HTTPException(404, "Institution not found")

        current = await db.fetchval("""
            SELECT COUNT(*) FROM institution_members
            WHERE institution_id = $1::uuid AND role = 'teacher' AND status = 'active'
        """, institution_id)

        if int(current or 0) >= inst["max_teachers"]:
            raise HTTPException(400, f"Teacher limit reached ({inst['max_teachers']}). Upgrade your plan.")

        # Create or find user
        teacher = await db.fetchrow(
            "SELECT id FROM users WHERE email = $1", req.email
        )
        if teacher:
            teacher_id = teacher["id"]
            await db.execute(
                "UPDATE users SET account_type = 'teacher' WHERE id = $1", teacher_id
            )
        else:
            teacher = await db.fetchrow("""
                INSERT INTO users (email, name, account_type, knowledge_level)
                VALUES ($1, $2, 'teacher', 'intermediate')
                RETURNING id
            """, req.email, req.name)
            teacher_id = teacher["id"]

        # Add to institution (or update if already pending)
        await db.execute("""
            INSERT INTO institution_members (institution_id, user_id, role, status, invited_by)
            VALUES ($1::uuid, $2, 'teacher', 'pending', $3::uuid)
            ON CONFLICT (institution_id, user_id) DO UPDATE SET status = 'pending', invited_by = $3::uuid
        """, institution_id, teacher_id, user_id)

        # Issue invite token
        raw_token = secrets.token_urlsafe(32)
        await db.execute("""
            INSERT INTO auth_tokens (user_id, token, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '7 days')
        """, teacher_id, raw_token)

    # TODO: send invitation email with verify token
    return {
        "message": f"Invitation sent to {req.email}",
        "verify_token": raw_token,  # dev: return token directly
    }


# ── Bulk import students ──────────────────────────────────────────────────────

class BulkStudentRow(BaseModel):
    email: EmailStr
    name:  str | None = None


class BulkStudentsRequest(BaseModel):
    students: list[BulkStudentRow]


@router.post("/{institution_id}/students/bulk")
async def bulk_import_students(
    institution_id: str,
    req: BulkStudentsRequest,
    authorization: str = Header(...),
):
    await _require_institution_admin(authorization)
    added = 0
    async with get_db() as db:
        inst = await db.fetchrow(
            "SELECT max_students FROM institutions WHERE id = $1::uuid", institution_id
        )
        if not inst:
            raise HTTPException(404, "Institution not found")

        current = await db.fetchval("""
            SELECT COUNT(*) FROM institution_members
            WHERE institution_id = $1::uuid AND role = 'student' AND status = 'active'
        """, institution_id)

        remaining = inst["max_students"] - int(current or 0)
        to_add = req.students[:remaining]

        for s in to_add:
            student = await db.fetchrow("SELECT id FROM users WHERE email = $1", s.email)
            if not student:
                student = await db.fetchrow("""
                    INSERT INTO users (email, name, account_type, knowledge_level)
                    VALUES ($1, $2, 'student', 'intermediate') RETURNING id
                """, s.email, s.name)
            await db.execute("""
                INSERT INTO institution_members (institution_id, user_id, role, status)
                VALUES ($1::uuid, $2, 'student', 'active')
                ON CONFLICT DO NOTHING
            """, institution_id, student["id"])
            added += 1

    return {"added": added, "skipped": len(req.students) - added}


# ── Suspend / reactivate member ───────────────────────────────────────────────

class MemberStatusRequest(BaseModel):
    status: str   # active | suspended


@router.patch("/{institution_id}/members/{member_user_id}")
async def update_member_status(
    institution_id: str,
    member_user_id: str,
    req: MemberStatusRequest,
    authorization: str = Header(...),
):
    if req.status not in ("active", "suspended"):
        raise HTTPException(400, "status must be 'active' or 'suspended'")
    await _require_institution_admin(authorization)
    async with get_db() as db:
        await db.execute("""
            UPDATE institution_members SET status = $1
            WHERE institution_id = $2::uuid AND user_id = $3::uuid
        """, req.status, institution_id, member_user_id)
    return {"ok": True}
