"""
Institution router — institution admin manages teachers and students.
All routes require account_type = 'institution_admin'.
"""
import re
import secrets
import string
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional

from database import get_db
from routers.auth import decode_jwt, _hash_password


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", ".", name.lower()).strip(".")


def _gen_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
from config import settings

_VALID_LANGUAGES = {'en', 'fi', 'sv', 'es', 'fr'}

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


# ── Institution language for any authenticated user ──────────────────────────

@router.get("/my-lang")
async def get_my_institution_language(authorization: str = Header(...)):
    """Returns the institution language for any member (student/teacher/admin)."""
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT i.language
            FROM institution_members im
            JOIN institutions i ON i.id = im.institution_id
            WHERE im.user_id = $1::uuid AND im.status = 'active'
            LIMIT 1
        """, user_id)
    return {"language": row["language"] if row else None}


# ── My institution (for institution_admin dashboard) ─────────────────────────

@router.get("/mine")
async def get_my_institution(authorization: str = Header(...)):
    user_id = await _require_institution_admin(authorization)
    async with get_db() as db:
        row = await db.fetchrow("""
            SELECT institution_id FROM institution_members
            WHERE user_id = $1::uuid AND role = 'admin' AND status = 'active'
        """, user_id)
        if not row:
            raise HTTPException(404, "No institution found for this admin")
        inst_id = str(row["institution_id"])
        inst = await db.fetchrow("SELECT * FROM institutions WHERE id = $1::uuid", inst_id)
        teacher_count = await db.fetchval("""
            SELECT COUNT(*) FROM institution_members
            WHERE institution_id = $1::uuid AND role = 'teacher' AND status = 'active'
        """, inst_id)
        student_count = await db.fetchval("""
            SELECT COUNT(*) FROM institution_members
            WHERE institution_id = $1::uuid AND role = 'student' AND status = 'active'
        """, inst_id)
    return {
        "id":            inst_id,
        "name":          inst["name"],
        "type":          inst["type"],
        "plan":          inst["plan"],
        "language":      inst["language"],
        "max_teachers":  inst["max_teachers"],
        "max_students":  inst["max_students"],
        "teacher_count": int(teacher_count or 0),
        "student_count": int(student_count or 0),
    }


# ── Update institution language ───────────────────────────────────────────────

class SetLanguageRequest(BaseModel):
    language: str | None = None


@router.patch("/mine/language")
async def set_institution_language(req: SetLanguageRequest, authorization: str = Header(...)):
    user_id = await _require_institution_admin(authorization)
    if req.language is not None and req.language not in _VALID_LANGUAGES:
        raise HTTPException(400, f"language must be one of: {', '.join(sorted(_VALID_LANGUAGES))}")
    async with get_db() as db:
        inst_id = await _get_admin_institution(user_id, db)
        await db.execute(
            "UPDATE institutions SET language = $1 WHERE id = $2::uuid",
            req.language, inst_id,
        )
    return {"language": req.language}


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


# ── Provision teacher with synthetic email ────────────────────────────────────

class ProvisionTeacherRequest(BaseModel):
    name:     str
    password: str = ""


@router.post("/{institution_id}/teachers/provision")
async def provision_teacher(
    institution_id: str,
    req:            ProvisionTeacherRequest,
    authorization:  str = Header(...),
):
    user_id = await _require_institution_admin(authorization)
    async with get_db() as db:
        inst = await db.fetchrow(
            "SELECT name, max_teachers FROM institutions WHERE id = $1::uuid", institution_id
        )
        if not inst:
            raise HTTPException(404, "Institution not found")

        current = await db.fetchval("""
            SELECT COUNT(*) FROM institution_members
            WHERE institution_id = $1::uuid AND role = 'teacher' AND status = 'active'
        """, institution_id)
        if int(current or 0) >= inst["max_teachers"]:
            raise HTTPException(400, f"Teacher limit reached ({inst['max_teachers']}). Upgrade your plan.")

        inst_slug  = _slug(inst["name"])
        name_slug  = _slug(req.name)
        base_email = f"{name_slug}.{inst_slug}@learnxai.app"
        taken      = await db.fetchrow("SELECT id FROM users WHERE email = $1", base_email)
        email      = f"{name_slug}.{inst_slug}.{secrets.token_hex(3)}@learnxai.app" if taken else base_email

        temp_password = req.password or _gen_password()
        pwd_hash      = _hash_password(temp_password)

        teacher = await db.fetchrow("""
            INSERT INTO users (email, name, account_type, knowledge_level, password_hash)
            VALUES ($1, $2, 'teacher', 'intermediate', $3)
            RETURNING id
        """, email, req.name, pwd_hash)

        await db.execute("""
            INSERT INTO institution_members (institution_id, user_id, role, status, invited_by)
            VALUES ($1::uuid, $2, 'teacher', 'active', $3::uuid)
            ON CONFLICT (institution_id, user_id) DO UPDATE SET status = 'active', invited_by = $3::uuid
        """, institution_id, teacher["id"], user_id)

    return {"name": req.name, "email": email, "password": temp_password}


# ── Invite a teacher (email-based, legacy) ────────────────────────────────────

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
