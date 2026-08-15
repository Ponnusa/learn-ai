"""
School Admin router — Sprint 1
Handles school creation and school admin authentication.
All endpoints require school_role = 'admin'.
"""
import logging
import secrets
import string
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

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
