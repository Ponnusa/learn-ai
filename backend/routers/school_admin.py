"""
School Admin router — Sprints 1-6
Handles school creation, admin auth, teacher invites, sections, course assignment,
student management, and student login.
All management endpoints require school_role = 'admin'.
"""
import csv
import io
import logging
import re
import secrets
import string
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Any

from config import settings

from database import get_db
from routers.auth import create_jwt, _hash_password, _verify_password
from routers.teacher_auth import get_current_teacher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/school", tags=["school-admin"])


# ── Auth helper ──────────────────────────────────────────────────────────────

async def _require_school_admin(authorization: str) -> dict:
    """Returns the user row if they are a school admin, else 403."""
    teacher = await get_current_teacher(authorization)
    async with get_db() as db:
        user = await db.fetchrow(
            "SELECT id, email, name, school_id, school_role FROM users WHERE id = $1::uuid",
            teacher["id"],
        )
    if not user or user["school_role"] != "admin":
        raise HTTPException(403, "School admin access required")
    return user


def _generate_school_code(name: str) -> str:
    """Generate a short unique-ish school code from name + random suffix."""
    prefix = "".join(c for c in name.upper() if c.isalpha())[:4]
    suffix = "".join(secrets.choice(string.digits) for _ in range(4))
    return f"{prefix}{suffix}"


# ── School creation (platform admin only — done manually for now) ────────────

class CreateSchoolRequest(BaseModel):
    name: str
    city: str | None = None
    country: str = "India"
    admin_email: str


@router.post("/create")
async def create_school(req: CreateSchoolRequest, authorization: str = Header(...)):
    """
    Create a new school and promote an existing user to school admin.
    For now this is restricted to platform-level (teacher_id must have is_admin flag).
    """
    teacher = await get_current_teacher(authorization)
    async with get_db() as db:
        account_type = await db.fetchval(
            "SELECT account_type FROM users WHERE id = $1::uuid", teacher["id"]
        )
    if account_type != "super_admin":
        raise HTTPException(403, "Platform admin access required")

    code = _generate_school_code(req.name)
    async with get_db() as db:
        # Ensure code is unique
        while await db.fetchval("SELECT 1 FROM schools WHERE code = $1", code):
            code = _generate_school_code(req.name)

        school = await db.fetchrow(
            """INSERT INTO schools (name, city, country, code)
               VALUES ($1, $2, $3, $4) RETURNING id, name, code""",
            req.name, req.city, req.country, code,
        )
        # Promote the admin user
        await db.execute(
            "UPDATE users SET school_id = $1, school_role = 'admin' WHERE email = $2",
            school["id"], req.admin_email,
        )

    logger.info("School created: %s (code=%s)", school["name"], school["code"])
    return {"id": str(school["id"]), "name": school["name"], "code": school["code"]}


# ── School admin dashboard ────────────────────────────────────────────────────

@router.get("/me")
async def get_school_info(authorization: str = Header(...)):
    """Return the school info for the logged-in school admin."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        school = await db.fetchrow(
            "SELECT id, name, city, country, code, created_at FROM schools WHERE id = $1",
            admin["school_id"],
        )
        teacher_count = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE school_id = $1 AND school_role = 'teacher'",
            admin["school_id"],
        )
        student_count = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE school_id = $1 AND school_role = 'student'",
            admin["school_id"],
        )

    return {
        "school": {
            "id":            str(school["id"]),
            "name":          school["name"],
            "city":          school["city"],
            "country":       school["country"],
            "code":          school["code"],
            "created_at":    school["created_at"].isoformat(),
        },
        "teacher_count": teacher_count,
        "student_count":  student_count,
    }


# ── Teacher management ────────────────────────────────────────────────────────

class AddTeacherRequest(BaseModel):
    email: str
    name: str | None = None


@router.post("/teachers/add")
async def add_teacher_to_school(req: AddTeacherRequest, authorization: str = Header(...)):
    """
    Link an existing user to this school as a teacher, or note them as pending
    if no account exists yet (Sprint 2 will handle invites).
    """
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        user = await db.fetchrow("SELECT id, name, school_id FROM users WHERE email = $1", req.email)
        if not user:
            raise HTTPException(404, "No account found for that email — they need to sign up first")
        if user["school_id"] and str(user["school_id"]) != str(admin["school_id"]):
            raise HTTPException(409, "This user already belongs to another school")
        await db.execute(
            "UPDATE users SET school_id = $1, school_role = 'teacher' WHERE id = $2",
            admin["school_id"], user["id"],
        )
    return {"ok": True, "teacher_id": str(user["id"]), "name": user["name"]}


@router.get("/teachers")
async def list_school_teachers(authorization: str = Header(...)):
    """List all teachers in this school."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch(
            """SELECT id, name, email, created_at
               FROM users
               WHERE school_id = $1 AND school_role = 'teacher'
               ORDER BY name""",
            admin["school_id"],
        )
    return [{"id": str(r["id"]), "name": r["name"], "email": r["email"]} for r in rows]


class CreateTeacherLoginRequest(BaseModel):
    name: str
    email: str
    password: str | None = None  # auto-generated if omitted


@router.post("/teachers/create")
async def create_teacher_login(req: CreateTeacherLoginRequest, authorization: str = Header(...)):
    """
    School admin creates a teacher account directly — no invite flow needed.
    If an account with that email already exists it is upgraded to teacher and
    linked to this school. Returns the temp password so admin can share it.
    """
    admin = await _require_school_admin(authorization)

    import secrets as _sec
    temp_password = req.password or _sec.token_urlsafe(8)
    pwd_hash = _hash_password(temp_password)

    async with get_db() as db:
        existing = await db.fetchrow("SELECT id, school_id FROM users WHERE email = $1", req.email)
        if existing:
            if existing["school_id"] and str(existing["school_id"]) != str(admin["school_id"]):
                raise HTTPException(409, "User already belongs to another school")
            await db.execute(
                """UPDATE users SET name = COALESCE(name, $1), account_type = 'teacher',
                   password_hash = COALESCE(password_hash, $2),
                   school_id = $3, school_role = 'teacher', is_active = true
                   WHERE id = $4""",
                req.name, pwd_hash, admin["school_id"], existing["id"],
            )
            user_id = str(existing["id"])
        else:
            row = await db.fetchrow(
                """INSERT INTO users
                     (name, email, account_type, knowledge_level, password_hash,
                      school_id, school_role, is_active)
                   VALUES ($1, $2, 'teacher', 'intermediate', $3, $4, 'teacher', true)
                   RETURNING id""",
                req.name, req.email, pwd_hash, admin["school_id"],
            )
            user_id = str(row["id"])

    return {
        "ok":           True,
        "teacher_id":   user_id,
        "email":        req.email,
        "temp_password": temp_password,
        "note":         "Share email + password with the teacher. They can change it from Settings.",
    }


@router.delete("/teachers/{teacher_id}")
async def remove_teacher_from_school(teacher_id: str, authorization: str = Header(...)):
    """Unlink a teacher from this school (doesn't delete their account)."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        result = await db.execute(
            """UPDATE users SET school_id = NULL, school_role = NULL
               WHERE id = $1::uuid AND school_id = $2 AND school_role = 'teacher'""",
            teacher_id, admin["school_id"],
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "Teacher not found in this school")
    return {"ok": True}


# ── Sprint 2: Invite system ───────────────────────────────────────────────────

class CreateInviteRequest(BaseModel):
    email: str | None = None   # optional — lock invite to one email
    role: str = "teacher"      # 'teacher' for now; 'admin' later
    expires_days: int = 7


@router.post("/invite")
async def create_invite(req: CreateInviteRequest, authorization: str = Header(...)):
    """
    Generate a one-time invite link for a teacher.
    If email is provided the invite is locked to that address.
    Returns a token the admin can share as a link:
      https://learnx-ai.com/join?invite=<token>
    """
    admin = await _require_school_admin(authorization)
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_days)

    async with get_db() as db:
        school = await db.fetchrow("SELECT name FROM schools WHERE id = $1", admin["school_id"])
        await db.execute(
            """INSERT INTO school_invites (token, school_id, email, role, created_by, expires_at)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            token, admin["school_id"], req.email, req.role, admin["id"], expires_at,
        )

    frontend_url = getattr(settings, "FRONTEND_URL", "https://learnx-ai.com")
    invite_url = f"{frontend_url}/join?invite={token}"
    return {
        "token":      token,
        "invite_url": invite_url,
        "school":     school["name"],
        "role":       req.role,
        "expires_at": expires_at.isoformat(),
    }


@router.get("/invite/{token}")
async def validate_invite(token: str):
    """
    Public endpoint — validate an invite token before showing the signup form.
    Returns school name and role so the frontend can pre-fill and label the form.
    """
    async with get_db() as db:
        invite = await db.fetchrow(
            """SELECT si.token, si.email, si.role, si.expires_at, si.accepted_at,
                      s.name AS school_name, s.city
               FROM school_invites si
               JOIN schools s ON s.id = si.school_id
               WHERE si.token = $1""",
            token,
        )
    if not invite:
        raise HTTPException(404, "Invite not found")
    if invite["accepted_at"]:
        raise HTTPException(410, "Invite already used")
    if invite["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(410, "Invite has expired")
    return {
        "school_name": invite["school_name"],
        "city":        invite["city"],
        "role":        invite["role"],
        "email":       invite["email"],  # None if open invite
    }


@router.post("/invite/{token}/accept")
async def accept_invite(token: str, authorization: str = Header(...)):
    """
    Called after a teacher logs in / signs up — links them to the school.
    The frontend calls this immediately after auth if an invite token is in the URL.
    """
    teacher = await get_current_teacher(authorization)
    async with get_db() as db:
        invite = await db.fetchrow(
            """SELECT school_id, email, role, expires_at, accepted_at
               FROM school_invites WHERE token = $1""",
            token,
        )
        if not invite:
            raise HTTPException(404, "Invite not found")
        if invite["accepted_at"]:
            raise HTTPException(410, "Invite already used")
        if invite["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(410, "Invite has expired")
        if invite["email"] and invite["email"].lower() != teacher["email"].lower():
            raise HTTPException(403, "This invite was sent to a different email address")

        user = await db.fetchrow("SELECT school_id FROM users WHERE id = $1::uuid", teacher["id"])
        if user["school_id"] and str(user["school_id"]) != str(invite["school_id"]):
            raise HTTPException(409, "You already belong to another school")

        await db.execute(
            "UPDATE users SET school_id = $1, school_role = $2 WHERE id = $3::uuid",
            invite["school_id"], invite["role"], teacher["id"],
        )
        await db.execute(
            "UPDATE school_invites SET accepted_by = $1, accepted_at = NOW() WHERE token = $2",
            teacher["id"], token,
        )
        school = await db.fetchrow("SELECT name, city FROM schools WHERE id = $1", invite["school_id"])

    return {"ok": True, "school_name": school["name"], "role": invite["role"]}


@router.get("/invites")
async def list_invites(authorization: str = Header(...)):
    """List all invites (pending and used) for this school."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch(
            """SELECT si.token, si.email, si.role, si.expires_at, si.accepted_at,
                      u.name AS accepted_by_name
               FROM school_invites si
               LEFT JOIN users u ON u.id = si.accepted_by
               WHERE si.school_id = $1
               ORDER BY si.created_at DESC""",
            admin["school_id"],
        )
    return [
        {
            "token":             r["token"],
            "email":             r["email"],
            "role":              r["role"],
            "status":            "used" if r["accepted_at"] else ("expired" if r["expires_at"] < datetime.now(timezone.utc) else "pending"),
            "accepted_by":       r["accepted_by_name"],
            "expires_at":        r["expires_at"].isoformat(),
        }
        for r in rows
    ]


# ── Sprint 2: School context for teacher ─────────────────────────────────────

@router.get("/context")
async def get_teacher_school_context(authorization: str = Header(...)):
    """
    Called by teacher dashboard on load — returns their school info if they
    belong to one. Returns null school if they're a standalone teacher.
    """
    teacher = await get_current_teacher(authorization)
    async with get_db() as db:
        user = await db.fetchrow(
            "SELECT school_id, school_role FROM users WHERE id = $1::uuid", teacher["id"]
        )
        if not user or not user["school_id"]:
            return {"school": None}
        school = await db.fetchrow(
            "SELECT id, name, city, country, code FROM schools WHERE id = $1",
            user["school_id"],
        )
    return {
        "school": {
            "id":      str(school["id"]),
            "name":    school["name"],
            "city":    school["city"],
            "country": school["country"],
            "code":    school["code"],
        },
        "role": user["school_role"],
    }


# ── Sprint 3: Sections ────────────────────────────────────────────────────────

class CreateSectionRequest(BaseModel):
    name: str            # e.g. "Grade 10 - A"
    grade: str | None = None          # e.g. "Grade 10"
    section_label: str | None = None  # e.g. "A"
    teacher_id: str | None = None     # assign immediately, or later


class UpdateSectionRequest(BaseModel):
    name: str | None = None
    grade: str | None = None
    section_label: str | None = None
    teacher_id: str | None = None     # pass empty string to unassign


def _section_row(r) -> dict:
    return {
        "id":            str(r["id"]),
        "name":          r["name"],
        "grade":         r["grade"],
        "section_label": r["section_label"],
        "teacher_id":    str(r["teacher_id"]) if r["teacher_id"] else None,
        "teacher_name":  r.get("teacher_name"),
        "student_count": r.get("student_count", 0),
        "created_at":    r["created_at"].isoformat(),
    }


@router.post("/sections")
async def create_section(req: CreateSectionRequest, authorization: str = Header(...)):
    """Admin creates a new section (class) in their school."""
    admin = await _require_school_admin(authorization)

    teacher_id = None
    if req.teacher_id:
        async with get_db() as db:
            ok = await db.fetchval(
                "SELECT 1 FROM users WHERE id = $1::uuid AND school_id = $2 AND school_role = 'teacher'",
                req.teacher_id, admin["school_id"],
            )
        if not ok:
            raise HTTPException(404, "Teacher not found in this school")
        teacher_id = req.teacher_id

    async with get_db() as db:
        row = await db.fetchrow(
            """INSERT INTO sections (school_id, name, grade, section_label, teacher_id)
               VALUES ($1, $2, $3, $4, $5::uuid)
               RETURNING id, name, grade, section_label, teacher_id, created_at""",
            admin["school_id"], req.name, req.grade, req.section_label, teacher_id,
        )
    return _section_row(dict(row))


@router.get("/sections")
async def list_sections(authorization: str = Header(...)):
    """Admin lists all sections in their school with teacher name and student count."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch(
            """SELECT s.id, s.name, s.grade, s.section_label, s.teacher_id, s.created_at,
                      u.name  AS teacher_name,
                      (SELECT COUNT(*) FROM users st
                       WHERE st.school_id = $1 AND st.school_role = 'student'
                         AND st.section_id = s.id) AS student_count
               FROM sections s
               LEFT JOIN users u ON u.id = s.teacher_id
               WHERE s.school_id = $1
               ORDER BY s.grade NULLS LAST, s.section_label, s.name""",
            admin["school_id"],
        )
    return [_section_row(dict(r)) for r in rows]


@router.patch("/sections/{section_id}")
async def update_section(section_id: str, req: UpdateSectionRequest, authorization: str = Header(...)):
    """Admin updates a section — rename, reassign teacher, or change grade."""
    admin = await _require_school_admin(authorization)

    async with get_db() as db:
        section = await db.fetchrow(
            "SELECT id FROM sections WHERE id = $1::uuid AND school_id = $2",
            section_id, admin["school_id"],
        )
        if not section:
            raise HTTPException(404, "Section not found")

        if req.teacher_id is not None:
            if req.teacher_id == "":
                teacher_id = None
            else:
                ok = await db.fetchval(
                    "SELECT 1 FROM users WHERE id = $1::uuid AND school_id = $2 AND school_role = 'teacher'",
                    req.teacher_id, admin["school_id"],
                )
                if not ok:
                    raise HTTPException(404, "Teacher not found in this school")
                teacher_id = req.teacher_id
        else:
            teacher_id = None  # don't touch existing

        # Build dynamic SET clause for only provided fields
        updates, params = [], [section_id]
        def _set(col, val):
            params.append(val)
            updates.append(f"{col} = ${len(params)}")

        if req.name          is not None: _set("name",          req.name)
        if req.grade         is not None: _set("grade",         req.grade)
        if req.section_label is not None: _set("section_label", req.section_label)
        if req.teacher_id    is not None: _set("teacher_id",    teacher_id)

        if updates:
            row = await db.fetchrow(
                f"UPDATE sections SET {', '.join(updates)} WHERE id = $1::uuid RETURNING id, name, grade, section_label, teacher_id, created_at",
                *params,
            )
        else:
            row = await db.fetchrow(
                "SELECT id, name, grade, section_label, teacher_id, created_at FROM sections WHERE id = $1::uuid",
                section_id,
            )
    return _section_row(dict(row))


@router.delete("/sections/{section_id}")
async def delete_section(section_id: str, authorization: str = Header(...)):
    """Admin deletes a section. Students in it lose their section assignment."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        result = await db.execute(
            "DELETE FROM sections WHERE id = $1::uuid AND school_id = $2",
            section_id, admin["school_id"],
        )
    if result == "DELETE 0":
        raise HTTPException(404, "Section not found")
    return {"ok": True}


@router.post("/sections/{section_id}/assign-teacher")
async def assign_teacher_to_section(section_id: str, req: AddTeacherRequest, authorization: str = Header(...)):
    """Shortcut: assign a teacher to a section by email."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        teacher = await db.fetchrow(
            "SELECT id FROM users WHERE email = $1 AND school_id = $2 AND school_role = 'teacher'",
            req.email, admin["school_id"],
        )
        if not teacher:
            raise HTTPException(404, "Teacher not found in this school")
        row = await db.fetchrow(
            """UPDATE sections SET teacher_id = $1 WHERE id = $2::uuid AND school_id = $3
               RETURNING id, name, grade, section_label, teacher_id, created_at""",
            teacher["id"], section_id, admin["school_id"],
        )
    if not row:
        raise HTTPException(404, "Section not found")
    return _section_row(dict(row))


# ── Teacher: see own sections ─────────────────────────────────────────────────

@router.get("/sections/mine")
async def get_my_sections(authorization: str = Header(...)):
    """
    Teacher calls this to see which sections they're assigned to.
    Returns empty list if they're not in a school.
    """
    teacher = await get_current_teacher(authorization)
    async with get_db() as db:
        user = await db.fetchrow(
            "SELECT school_id, school_role FROM users WHERE id = $1::uuid", teacher["id"]
        )
        if not user or not user["school_id"]:
            return []
        rows = await db.fetch(
            """SELECT s.id, s.name, s.grade, s.section_label, s.teacher_id, s.created_at,
                      (SELECT COUNT(*) FROM users st
                       WHERE st.section_id = s.id AND st.school_role = 'student') AS student_count
               FROM sections s
               WHERE s.teacher_id = $1::uuid AND s.school_id = $2
               ORDER BY s.grade NULLS LAST, s.section_label""",
            teacher["id"], user["school_id"],
        )
    return [_section_row(dict(r)) for r in rows]


# ── Sprint 4: Course assignment ───────────────────────────────────────────────

class AssignCourseRequest(BaseModel):
    course_id: str


class AssignSectionCourseRequest(BaseModel):
    school_course_id: str


def _course_row(r) -> dict:
    return {
        "school_course_id": str(r["school_course_id"]),
        "course_id":        str(r["course_id"]),
        "course_name":      r["course_name"],
        "subject":          r.get("subject"),
        "grade":            r.get("grade"),
        "created_at":       r["created_at"].isoformat(),
    }


@router.post("/courses/assign")
async def assign_course_to_school(req: AssignCourseRequest, authorization: str = Header(...)):
    """Admin designates an existing course as a school master course."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        course = await db.fetchrow(
            "SELECT id, name FROM courses WHERE id = $1::uuid", req.course_id
        )
        if not course:
            raise HTTPException(404, "Course not found")
        row = await db.fetchrow(
            """INSERT INTO school_courses (school_id, course_id, assigned_by)
               VALUES ($1, $2::uuid, $3::uuid)
               ON CONFLICT (school_id, course_id) DO UPDATE SET assigned_by = EXCLUDED.assigned_by
               RETURNING id, created_at""",
            admin["school_id"], req.course_id, admin["id"],
        )
    return {"school_course_id": str(row["id"]), "course_name": course["name"]}


@router.get("/courses")
async def list_school_courses(authorization: str = Header(...)):
    """Admin lists all courses assigned to their school."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch(
            """SELECT sc.id AS school_course_id, sc.course_id, sc.created_at,
                      c.name AS course_name, c.subject, c.grade
               FROM school_courses sc
               JOIN courses c ON c.id = sc.course_id
               WHERE sc.school_id = $1
               ORDER BY c.name""",
            admin["school_id"],
        )
    return [_course_row(dict(r)) for r in rows]


@router.delete("/courses/{school_course_id}")
async def unassign_course_from_school(school_course_id: str, authorization: str = Header(...)):
    """Remove a course from the school (cascades to all section assignments)."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        result = await db.execute(
            "DELETE FROM school_courses WHERE id = $1::uuid AND school_id = $2",
            school_course_id, admin["school_id"],
        )
    if result == "DELETE 0":
        raise HTTPException(404, "School course not found")
    return {"ok": True}


@router.post("/sections/{section_id}/courses")
async def assign_course_to_section(
    section_id: str,
    req: AssignSectionCourseRequest,
    authorization: str = Header(...),
):
    """Assign a school master course to a specific section."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        section = await db.fetchrow(
            "SELECT id FROM sections WHERE id = $1::uuid AND school_id = $2",
            section_id, admin["school_id"],
        )
        if not section:
            raise HTTPException(404, "Section not found")
        sc = await db.fetchrow(
            "SELECT id FROM school_courses WHERE id = $1::uuid AND school_id = $2",
            req.school_course_id, admin["school_id"],
        )
        if not sc:
            raise HTTPException(404, "School course not found")
        await db.execute(
            """INSERT INTO section_courses (section_id, school_course_id)
               VALUES ($1::uuid, $2::uuid)
               ON CONFLICT (section_id, school_course_id) DO NOTHING""",
            section_id, req.school_course_id,
        )
    return {"ok": True}


@router.get("/sections/{section_id}/courses")
async def list_section_courses(section_id: str, authorization: str = Header(...)):
    """Admin sees which courses are assigned to a section."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        section = await db.fetchrow(
            "SELECT id FROM sections WHERE id = $1::uuid AND school_id = $2",
            section_id, admin["school_id"],
        )
        if not section:
            raise HTTPException(404, "Section not found")
        rows = await db.fetch(
            """SELECT sc.id AS school_course_id, sc.course_id, sc.created_at,
                      c.name AS course_name, c.subject, c.grade
               FROM section_courses scc
               JOIN school_courses sc ON sc.id = scc.school_course_id
               JOIN courses c ON c.id = sc.course_id
               WHERE scc.section_id = $1::uuid
               ORDER BY c.name""",
            section_id,
        )
    return [_course_row(dict(r)) for r in rows]


@router.delete("/sections/{section_id}/courses/{school_course_id}")
async def unassign_course_from_section(
    section_id: str,
    school_course_id: str,
    authorization: str = Header(...),
):
    """Remove a course from a specific section."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        section = await db.fetchrow(
            "SELECT id FROM sections WHERE id = $1::uuid AND school_id = $2",
            section_id, admin["school_id"],
        )
        if not section:
            raise HTTPException(404, "Section not found")
        await db.execute(
            "DELETE FROM section_courses WHERE section_id = $1::uuid AND school_course_id = $2::uuid",
            section_id, school_course_id,
        )
    return {"ok": True}


# ── Teacher: see courses for their sections ───────────────────────────────────

@router.get("/my-courses")
async def get_my_section_courses(authorization: str = Header(...)):
    """
    Teacher calls this to see all courses assigned to their sections, grouped by section.
    Existing self-created courses are fetched separately via /api/courses.
    """
    teacher = await get_current_teacher(authorization)
    async with get_db() as db:
        user = await db.fetchrow(
            "SELECT school_id, school_role FROM users WHERE id = $1::uuid", teacher["id"]
        )
        if not user or not user["school_id"]:
            return []
        rows = await db.fetch(
            """SELECT
                  s.id            AS section_id,
                  s.name          AS section_name,
                  s.grade,
                  s.section_label,
                  sc.id           AS school_course_id,
                  c.id            AS course_id,
                  c.name          AS course_name,
                  c.subject,
                  c.grade         AS course_grade
               FROM sections s
               JOIN section_courses scc ON scc.section_id = s.id
               JOIN school_courses sc   ON sc.id = scc.school_course_id
               JOIN courses c           ON c.id  = sc.course_id
               WHERE s.teacher_id = $1::uuid AND s.school_id = $2
               ORDER BY s.grade NULLS LAST, s.section_label, c.name""",
            teacher["id"], user["school_id"],
        )

    sections: dict[str, dict] = {}
    for r in rows:
        sid = str(r["section_id"])
        if sid not in sections:
            sections[sid] = {
                "section_id":    sid,
                "section_name":  r["section_name"],
                "grade":         r["grade"],
                "section_label": r["section_label"],
                "courses":       [],
            }
        sections[sid]["courses"].append({
            "school_course_id": str(r["school_course_id"]),
            "course_id":        str(r["course_id"]),
            "course_name":      r["course_name"],
            "subject":          r["subject"],
        })
    return list(sections.values())


# ── Sprint 6: Student management ──────────────────────────────────────────────

def _make_roll_password(roll_number: str) -> str:
    """Default first-login password = roll number itself (student must change)."""
    return roll_number


def _student_login_key(school_code: str, roll_number: str) -> str:
    return f"{school_code.upper().strip()}:{roll_number.strip()}"


class CreateStudentRequest(BaseModel):
    name: str
    roll_number: str
    email: str | None = None  # auto-generated if omitted
    section_id: str | None = None
    password: str | None = None  # defaults to roll number


class BulkImportRequest(BaseModel):
    section_id: str
    # List of {name, roll_number} dicts — also accepts raw CSV text via csv_text
    students: list[dict[str, str]] = Field(default_factory=list)
    csv_text: str | None = None  # "name,roll_number\nAlice,001\nBob,002"


class StudentLoginRequest(BaseModel):
    school_code: str
    roll_number: str
    password: str


def _student_row(r) -> dict:
    return {
        "id":          str(r["id"]),
        "name":        r["name"],
        "roll_number": r["roll_number"],
        "section_id":  str(r["section_id"]) if r.get("section_id") else None,
        "section_name": r.get("section_name"),
        "is_active":   r["is_active"],
        "created_at":  r["created_at"].isoformat(),
    }


@router.post("/students")
async def create_student(req: CreateStudentRequest, authorization: str = Header(...)):
    """Admin creates a single student account in their school."""
    admin = await _require_school_admin(authorization)

    if req.section_id:
        async with get_db() as db:
            ok = await db.fetchval(
                "SELECT 1 FROM sections WHERE id = $1::uuid AND school_id = $2",
                req.section_id, admin["school_id"],
            )
        if not ok:
            raise HTTPException(404, "Section not found in this school")

    school_code = await _get_school_code(admin["school_id"])
    roll = req.roll_number.strip()
    password = req.password or _make_roll_password(roll)
    email = (req.email or "").strip() or f"{school_code.lower()}.{roll.lower().replace(' ', '_')}@students.learnxai.internal"

    async with get_db() as db:
        existing = await db.fetchval(
            "SELECT 1 FROM users WHERE school_id = $1 AND roll_number = $2",
            admin["school_id"], roll,
        )
        if existing:
            raise HTTPException(409, f"Roll number {roll!r} already exists in this school")

        row = await db.fetchrow(
            """INSERT INTO users
                 (name, email, account_type, school_id, school_role, section_id, roll_number,
                  password_hash, is_active, tier, knowledge_level)
               VALUES ($1, $2, 'student', $3, 'student', $4::uuid, $5, $6, true, 'free', 'beginner')
               RETURNING id, name, roll_number, section_id, is_active, created_at""",
            req.name, email, admin["school_id"], req.section_id, roll, _hash_password(password),
        )
    return {**_student_row(dict(row)), "password_set": password}


@router.post("/students/bulk-import")
async def bulk_import_students(req: BulkImportRequest, authorization: str = Header(...)):
    """
    Bulk-create student accounts from a list or CSV text.
    All students are assigned to the given section.
    Returns per-row results so the admin can see which rows succeeded or failed.
    """
    admin = await _require_school_admin(authorization)

    # Validate section
    async with get_db() as db:
        section = await db.fetchrow(
            "SELECT id, name FROM sections WHERE id = $1::uuid AND school_id = $2",
            req.section_id, admin["school_id"],
        )
    if not section:
        raise HTTPException(404, "Section not found in this school")

    school_code = await _get_school_code(admin["school_id"])

    # Parse CSV if provided
    students = list(req.students)
    if req.csv_text:
        reader = csv.DictReader(io.StringIO(req.csv_text.strip()))
        for r in reader:
            name = r.get("name") or r.get("Name") or ""
            roll = r.get("roll_number") or r.get("roll") or r.get("Roll") or ""
            if name.strip() and roll.strip():
                students.append({"name": name.strip(), "roll_number": roll.strip()})

    if not students:
        raise HTTPException(400, "No students provided")

    results = []
    async with get_db() as db:
        for s in students:
            name = s.get("name", "").strip()
            roll = s.get("roll_number", "").strip()
            if not name or not roll:
                results.append({"roll_number": roll, "status": "error", "reason": "Missing name or roll_number"})
                continue
            try:
                existing = await db.fetchval(
                    "SELECT 1 FROM users WHERE school_id = $1 AND roll_number = $2",
                    admin["school_id"], roll,
                )
                if existing:
                    results.append({"roll_number": roll, "status": "skipped", "reason": "Roll number already exists"})
                    continue
                password = _make_roll_password(roll)
                bulk_email = s.get("email", "").strip() or f"{school_code.lower()}.{roll.lower().replace(' ', '_')}@students.learnxai.internal"
                await db.execute(
                    """INSERT INTO users
                         (name, email, account_type, school_id, school_role, section_id, roll_number,
                          password_hash, is_active, tier, knowledge_level)
                       VALUES ($1, $2, 'student', $3, 'student', $4::uuid, $5, $6, true, 'free', 'beginner')""",
                    name, bulk_email, admin["school_id"], req.section_id, roll, _hash_password(password),
                )
                results.append({
                    "name":        name,
                    "roll_number": roll,
                    "password":    password,
                    "status":      "created",
                })
            except Exception as exc:
                results.append({"roll_number": roll, "status": "error", "reason": str(exc)})

    created = sum(1 for r in results if r["status"] == "created")
    return {"created": created, "total": len(students), "results": results}


@router.get("/students")
async def list_students(
    authorization: str = Header(...),
    section_id: str | None = None,
):
    """Admin lists all students in their school, optionally filtered by section."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        if section_id:
            rows = await db.fetch(
                """SELECT u.id, u.name, u.roll_number, u.section_id, u.is_active, u.created_at,
                          s.name AS section_name
                   FROM users u
                   LEFT JOIN sections s ON s.id = u.section_id
                   WHERE u.school_id = $1 AND u.school_role = 'student' AND u.section_id = $2::uuid
                   ORDER BY u.name""",
                admin["school_id"], section_id,
            )
        else:
            rows = await db.fetch(
                """SELECT u.id, u.name, u.roll_number, u.section_id, u.is_active, u.created_at,
                          s.name AS section_name
                   FROM users u
                   LEFT JOIN sections s ON s.id = u.section_id
                   WHERE u.school_id = $1 AND u.school_role = 'student'
                   ORDER BY s.name NULLS LAST, u.name""",
                admin["school_id"],
            )
    return [_student_row(dict(r)) for r in rows]


@router.patch("/students/{student_id}")
async def update_student(
    student_id: str,
    req: CreateStudentRequest,
    authorization: str = Header(...),
):
    """Update a student's name, section, or reset their password."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        student = await db.fetchrow(
            "SELECT id FROM users WHERE id = $1::uuid AND school_id = $2 AND school_role = 'student'",
            student_id, admin["school_id"],
        )
        if not student:
            raise HTTPException(404, "Student not found")

        updates, params = [], [student_id]
        def _set(col, val):
            params.append(val)
            updates.append(f"{col} = ${len(params)}")

        if req.name:          _set("name",        req.name)
        if req.roll_number:   _set("roll_number", req.roll_number.strip())
        if req.section_id is not None:
            _set("section_id", req.section_id or None)
        if req.password:
            _set("password_hash", _hash_password(req.password))

        if updates:
            await db.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = $1::uuid",
                *params,
            )
    return {"ok": True}


@router.delete("/students/{student_id}")
async def delete_student(student_id: str, authorization: str = Header(...)):
    """Remove a student account from the school."""
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        result = await db.execute(
            "DELETE FROM users WHERE id = $1::uuid AND school_id = $2 AND school_role = 'student'",
            student_id, admin["school_id"],
        )
    if result == "DELETE 0":
        raise HTTPException(404, "Student not found")
    return {"ok": True}


# ── Student login (school code + roll number) ─────────────────────────────────

@router.post("/student-login")
async def student_login(req: StudentLoginRequest):
    """
    Student logs in with school code + roll number + password.
    Returns the same {token, user} shape as other login methods.
    """
    school_code = req.school_code.upper().strip()
    roll = req.roll_number.strip()

    async with get_db() as db:
        school = await db.fetchrow(
            "SELECT id FROM schools WHERE UPPER(code) = $1", school_code
        )
        if not school:
            raise HTTPException(401, "Invalid school code")

        user = await db.fetchrow(
            """SELECT id, name, roll_number, password_hash, is_active,
                      tier, theme, language, account_type, school_role, section_id
               FROM users
               WHERE school_id = $1 AND roll_number = $2 AND school_role = 'student'""",
            school["id"], roll,
        )
        if not user:
            raise HTTPException(401, "Invalid roll number or school code")
        if not user["is_active"]:
            raise HTTPException(403, "Account is inactive — contact your teacher")
        if not user["password_hash"] or not _verify_password(req.password, user["password_hash"]):
            raise HTTPException(401, "Incorrect password")

        token = create_jwt(str(user["id"]))
        await db.execute(
            "UPDATE users SET last_seen_at = NOW() WHERE id = $1", user["id"]
        )

    return {
        "token": token,
        "user": {
            "id":           str(user["id"]),
            "name":         user["name"],
            "roll_number":  user["roll_number"],
            "account_type": user["account_type"],
            "school_role":  user["school_role"],
            "section_id":   str(user["section_id"]) if user["section_id"] else None,
            "tier":         user["tier"],
            "theme":        user["theme"] or "dark",
            "language":     user["language"] or "en",
        },
    }


# ── Sprint 7: Admin dashboard ─────────────────────────────────────────────────

@router.get("/dashboard")
async def get_admin_dashboard(authorization: str = Header(...)):
    """
    Full dashboard snapshot for school admin:
    school info, aggregate stats, per-section breakdown with teacher + courses.
    """
    admin = await _require_school_admin(authorization)
    sid = admin["school_id"]

    async with get_db() as db:
        school = await db.fetchrow(
            "SELECT id, name, city, country, code, created_at FROM schools WHERE id = $1", sid
        )

        teacher_count = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE school_id = $1 AND school_role = 'teacher'", sid
        )
        student_count = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE school_id = $1 AND school_role = 'student'", sid
        )
        section_count = await db.fetchval(
            "SELECT COUNT(*) FROM sections WHERE school_id = $1", sid
        )
        course_count = await db.fetchval(
            "SELECT COUNT(*) FROM school_courses WHERE school_id = $1", sid
        )

        # Per-section: teacher name, student count, assigned courses
        sections = await db.fetch(
            """SELECT
                  s.id, s.name, s.grade, s.section_label,
                  t.id   AS teacher_id,
                  t.name AS teacher_name,
                  t.email AS teacher_email,
                  (SELECT COUNT(*) FROM users st
                   WHERE st.section_id = s.id AND st.school_role = 'student') AS student_count
               FROM sections s
               LEFT JOIN users t ON t.id = s.teacher_id
               WHERE s.school_id = $1
               ORDER BY s.grade NULLS LAST, s.section_label, s.name""",
            sid,
        )

        # Courses per section
        section_ids = [str(r["id"]) for r in sections]
        section_courses_rows = []
        if section_ids:
            section_courses_rows = await db.fetch(
                """SELECT scc.section_id, c.id AS course_id, c.name AS course_name, c.subject
                   FROM section_courses scc
                   JOIN school_courses sc ON sc.id = scc.school_course_id
                   JOIN courses c ON c.id = sc.course_id
                   WHERE scc.section_id = ANY($1::uuid[])
                   ORDER BY c.name""",
                [r["id"] for r in sections],
            )

    # Group courses by section
    courses_by_section: dict[str, list] = {}
    for r in section_courses_rows:
        k = str(r["section_id"])
        courses_by_section.setdefault(k, []).append({
            "course_id":   str(r["course_id"]),
            "course_name": r["course_name"],
            "subject":     r["subject"],
        })

    section_list = [
        {
            "id":            str(s["id"]),
            "name":          s["name"],
            "grade":         s["grade"],
            "section_label": s["section_label"],
            "teacher":       {"id": str(s["teacher_id"]), "name": s["teacher_name"], "email": s["teacher_email"]} if s["teacher_id"] else None,
            "student_count": int(s["student_count"]),
            "courses":       courses_by_section.get(str(s["id"]), []),
        }
        for s in sections
    ]

    return {
        "school": {
            "id":         str(school["id"]),
            "name":       school["name"],
            "city":       school["city"],
            "country":    school["country"],
            "code":       school["code"],
            "created_at": school["created_at"].isoformat(),
        },
        "stats": {
            "teachers": int(teacher_count),
            "students": int(student_count),
            "sections": int(section_count),
            "courses":  int(course_count),
        },
        "sections": section_list,
    }


# ── Sprint 7: View + promote teacher content ──────────────────────────────────

@router.get("/sections/{section_id}/teacher-content")
async def list_section_teacher_content(
    section_id: str,
    concept_id: str,
    authorization: str = Header(...),
):
    """
    Admin views teacher-authored blocks for a specific concept in a section.
    Returns only origin='teacher' blocks so admin can decide what to promote.
    """
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        section = await db.fetchrow(
            "SELECT id FROM sections WHERE id = $1::uuid AND school_id = $2",
            section_id, admin["school_id"],
        )
        if not section:
            raise HTTPException(404, "Section not found")

        rows = await db.fetch(
            """SELECT cb.id, cb.type, cb.position, cb.title, cb.body, cb.origin,
                      cb.created_at, u.name AS created_by_name
               FROM concept_content_blocks cb
               LEFT JOIN users u ON u.id = cb.created_by
               WHERE cb.concept_id = $1::uuid
                 AND cb.section_id = $2::uuid
                 AND cb.origin = 'teacher'
                 AND cb.in_textbook = true
               ORDER BY cb.position, cb.created_at""",
            concept_id, section_id,
        )
    return [
        {
            "id":              str(r["id"]),
            "type":            r["type"],
            "position":        r["position"],
            "title":           r["title"],
            "body":            r["body"],
            "origin":          r["origin"],
            "created_by_name": r["created_by_name"],
            "created_at":      r["created_at"].isoformat(),
        }
        for r in rows
    ]


@router.post("/content-blocks/{block_id}/promote")
async def promote_block_to_admin(block_id: str, authorization: str = Header(...)):
    """
    Admin promotes a teacher-authored block to admin origin.
    Effect: origin='admin', section_id=NULL — now visible to ALL sections that have this course.
    The original section-local block is effectively replaced by the promoted master.
    """
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        # Confirm the block belongs to a concept in a section owned by this school
        block = await db.fetchrow(
            """SELECT cb.id, cb.concept_id, cb.origin, cb.section_id,
                      s.school_id
               FROM concept_content_blocks cb
               LEFT JOIN sections s ON s.id = cb.section_id
               WHERE cb.id = $1::uuid""",
            block_id,
        )
        if not block:
            raise HTTPException(404, "Block not found")
        if block["origin"] == "admin":
            return {"ok": True, "message": "Already an admin block"}
        if block["school_id"] and str(block["school_id"]) != str(admin["school_id"]):
            raise HTTPException(403, "Block belongs to a different school")

        await db.execute(
            "UPDATE concept_content_blocks SET origin = 'admin', section_id = NULL WHERE id = $1::uuid",
            block_id,
        )
    return {"ok": True, "block_id": block_id}


@router.post("/content-blocks/{block_id}/demote")
async def demote_block_to_teacher(
    block_id: str,
    section_id: str,
    authorization: str = Header(...),
):
    """
    Admin reverts a promoted block back to section-local teacher content.
    Requires the target section_id to re-assign it to.
    """
    admin = await _require_school_admin(authorization)
    async with get_db() as db:
        block = await db.fetchrow(
            "SELECT id, origin FROM concept_content_blocks WHERE id = $1::uuid",
            block_id,
        )
        if not block:
            raise HTTPException(404, "Block not found")
        if block["origin"] != "admin":
            raise HTTPException(400, "Block is not an admin block")

        section = await db.fetchrow(
            "SELECT id FROM sections WHERE id = $1::uuid AND school_id = $2",
            section_id, admin["school_id"],
        )
        if not section:
            raise HTTPException(404, "Section not found")

        await db.execute(
            "UPDATE concept_content_blocks SET origin = 'teacher', section_id = $1::uuid WHERE id = $2::uuid",
            section_id, block_id,
        )
    return {"ok": True, "block_id": block_id}


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_school_code(school_id) -> str:
    async with get_db() as db:
        return await db.fetchval("SELECT code FROM schools WHERE id = $1", school_id) or ""
