"""
School Admin router — Sprint 1 + 2
Handles school creation, admin auth, teacher invites, school context.
All management endpoints require school_role = 'admin'.
"""
import logging
import secrets
import string
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import settings

from database import get_db
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
