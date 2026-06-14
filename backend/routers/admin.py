"""
Super admin router — review applications, approve/reject, generate invite codes, platform stats.
All routes require account_type = 'super_admin'.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from database import get_db
from routers.auth import decode_jwt

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _require_super_admin(authorization: str = Header(...)):
    user_id = decode_jwt(authorization.removeprefix("Bearer ").strip())
    async with get_db() as db:
        row = await db.fetchrow(
            "SELECT account_type FROM users WHERE id = $1::uuid", user_id
        )
    if not row or row["account_type"] != "super_admin":
        raise HTTPException(403, "Super admin access required")
    return user_id


# ── Platform stats ────────────────────────────────────────────────────────────

@router.get("/stats")
async def platform_stats(authorization: str = Header(...)):
    await _require_super_admin(authorization)
    async with get_db() as db:
        users_total     = await db.fetchval("SELECT COUNT(*) FROM users")
        teachers_total  = await db.fetchval("SELECT COUNT(*) FROM users WHERE account_type = 'teacher'")
        institutions    = await db.fetchval("SELECT COUNT(*) FROM institutions")
        pending_apps    = await db.fetchval("SELECT COUNT(*) FROM teacher_applications WHERE status = 'pending'")
        unused_invites  = await db.fetchval("SELECT COUNT(*) FROM teacher_invites WHERE used_at IS NULL AND expires_at > NOW()")

    return {
        "users_total":    int(users_total or 0),
        "teachers_total": int(teachers_total or 0),
        "institutions":   int(institutions or 0),
        "pending_applications": int(pending_apps or 0),
        "unused_invites": int(unused_invites or 0),
    }


# ── Applications ──────────────────────────────────────────────────────────────

@router.get("/applications")
async def list_applications(
    status: str = "pending",
    authorization: str = Header(...),
):
    await _require_super_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT id, type, name, email, school_name, subject, inst_type,
                   country, est_teachers, est_students, email_domain,
                   message, status, created_at
            FROM teacher_applications
            WHERE status = $1
            ORDER BY created_at ASC
        """, status)
    return [
        {
            "id":           str(r["id"]),
            "type":         r["type"],
            "name":         r["name"],
            "email":        r["email"],
            "school_name":  r["school_name"],
            "subject":      r["subject"],
            "inst_type":    r["inst_type"],
            "country":      r["country"],
            "est_teachers": r["est_teachers"],
            "est_students": r["est_students"],
            "email_domain": r["email_domain"],
            "message":      r["message"],
            "status":       r["status"],
            "created_at":   r["created_at"].isoformat(),
        }
        for r in rows
    ]


class ReviewApplicationRequest(BaseModel):
    action:        str          # approve | reject
    reject_reason: str | None = None


@router.post("/applications/{application_id}/review")
async def review_application(
    application_id: str,
    req: ReviewApplicationRequest,
    authorization: str = Header(...),
):
    if req.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be 'approve' or 'reject'")
    admin_id = await _require_super_admin(authorization)

    async with get_db() as db:
        app = await db.fetchrow(
            "SELECT * FROM teacher_applications WHERE id = $1::uuid", application_id
        )
        if not app:
            raise HTTPException(404, "Application not found")
        if app["status"] != "pending":
            raise HTTPException(400, f"Application is already {app['status']}")

        await db.execute("""
            UPDATE teacher_applications
            SET status = $1, reviewed_by = $2::uuid, reviewed_at = NOW(), reject_reason = $3
            WHERE id = $4::uuid
        """, req.action + "d", admin_id, req.reject_reason, application_id)

        invite_code = None
        if req.action == "approve" and app["type"] == "standalone":
            # Auto-generate an invite code for the applicant
            row = await db.fetchrow("""
                INSERT INTO teacher_invites (email, note, created_by)
                VALUES ($1, $2, $3::uuid)
                RETURNING code
            """, app["email"], f"Auto-issued for approved application {application_id}", admin_id)
            invite_code = row["code"]

        elif req.action == "approve" and app["type"] == "institution":
            # Create the institution and admin user
            inst = await db.fetchrow("""
                INSERT INTO institutions (name, type, email_domain, country, plan)
                VALUES ($1, $2, $3, $4, 'trial')
                RETURNING id
            """, app["school_name"], app["inst_type"], app["email_domain"], app["country"])

            # Create or find admin user
            user = await db.fetchrow("SELECT id FROM users WHERE email = $1", app["email"])
            if not user:
                user = await db.fetchrow("""
                    INSERT INTO users (email, name, account_type, knowledge_level)
                    VALUES ($1, $2, 'institution_admin', 'intermediate') RETURNING id
                """, app["email"], app["name"])
            else:
                await db.execute(
                    "UPDATE users SET account_type = 'institution_admin' WHERE id = $1", user["id"]
                )

            await db.execute("""
                INSERT INTO institution_members (institution_id, user_id, role, status, invited_by)
                VALUES ($1, $2, 'admin', 'active', $3::uuid)
                ON CONFLICT DO NOTHING
            """, inst["id"], user["id"], admin_id)

    result = {"ok": True, "action": req.action}
    if invite_code:
        result["invite_code"] = invite_code
    return result


# ── Invite codes ──────────────────────────────────────────────────────────────

class CreateInviteRequest(BaseModel):
    email: str | None = None
    note:  str | None = None


@router.post("/invites")
async def create_invite(req: CreateInviteRequest, authorization: str = Header(...)):
    admin_id = await _require_super_admin(authorization)
    async with get_db() as db:
        row = await db.fetchrow("""
            INSERT INTO teacher_invites (email, note, created_by)
            VALUES ($1, $2, $3::uuid)
            RETURNING id, code, expires_at
        """, req.email, req.note, admin_id)
    return {
        "id":         str(row["id"]),
        "code":       row["code"],
        "expires_at": row["expires_at"].isoformat(),
    }


@router.get("/invites")
async def list_invites(authorization: str = Header(...)):
    await _require_super_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT ti.id, ti.code, ti.email, ti.note, ti.used_at, ti.expires_at,
                   u.email AS used_by_email
            FROM teacher_invites ti
            LEFT JOIN users u ON u.id = ti.used_by
            ORDER BY ti.created_at DESC
            LIMIT 100
        """)
    return [
        {
            "id":            str(r["id"]),
            "code":          r["code"],
            "email":         r["email"],
            "note":          r["note"],
            "used_at":       r["used_at"].isoformat() if r["used_at"] else None,
            "expires_at":    r["expires_at"].isoformat(),
            "used_by_email": r["used_by_email"],
        }
        for r in rows
    ]


# ── Institutions list ─────────────────────────────────────────────────────────

@router.get("/institutions")
async def list_institutions(authorization: str = Header(...)):
    await _require_super_admin(authorization)
    async with get_db() as db:
        rows = await db.fetch("""
            SELECT i.id, i.name, i.type, i.plan, i.country,
                   i.max_teachers, i.max_students, i.created_at,
                   COUNT(CASE WHEN im.role = 'teacher' AND im.status = 'active' THEN 1 END) AS teacher_count,
                   COUNT(CASE WHEN im.role = 'student' AND im.status = 'active' THEN 1 END) AS student_count
            FROM institutions i
            LEFT JOIN institution_members im ON im.institution_id = i.id
            GROUP BY i.id
            ORDER BY i.created_at DESC
        """)
    return [
        {
            "id":            str(r["id"]),
            "name":          r["name"],
            "type":          r["type"],
            "plan":          r["plan"],
            "country":       r["country"],
            "max_teachers":  r["max_teachers"],
            "max_students":  r["max_students"],
            "teacher_count": int(r["teacher_count"] or 0),
            "student_count": int(r["student_count"] or 0),
            "created_at":    r["created_at"].isoformat(),
        }
        for r in rows
    ]
